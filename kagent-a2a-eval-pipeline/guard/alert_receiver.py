#!/usr/bin/env python3
"""Webhook receiver for Grafana-managed alerting (or Alertmanager): the plain-code handler between an alert and the overseer agent.

Grafana contact point (type webhook) POSTs here. This process:
  1. checks a bearer token (env ALERT_RECEIVER_TOKEN; refuses to start without one), a size cap and the JSON shape;
  2. runs alert_to_a2a.py (human-only alerts never reach an agent, no self-trigger, dedupe, spend guards, breaker);
  3. by default STOPS there: request files sit in --outbox for a person or a job to review. With --send-url it sends at most
     --max-sends requests per webhook call to the agent gateway, then records each outcome (tokens, failures) in the breaker.
It never loops: one webhook call = at most --max-sends agent runs. Exit/HTTP: 200 handled, 401 bad token, 400 bad body, 413 too big.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

HERE = Path(__file__).resolve().parent
MAX_BODY = 256 * 1024
_LOCK = Lock()  # one webhook at a time: the breaker is check-then-act


def handle(body: bytes, a: argparse.Namespace, token_ok: bool, enqueue=None) -> tuple[int, dict]:
    if not token_ok:
        return 401, {"error": "bad token"}
    if len(body) > MAX_BODY:
        return 413, {"error": "payload too large"}
    try:
        doc = json.loads(body)
        if not isinstance(doc.get("alerts"), list):
            raise ValueError("alerts must be a list")
    except (ValueError, AttributeError) as exc:
        return 400, {"error": str(exc)}
    stamp = f"{int(time.time())}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    a.spool.mkdir(parents=True, exist_ok=True)
    payload = a.spool / f"payload-{stamp}.json"
    payload.write_bytes(body)
    out = a.outbox / stamp
    cmd = [sys.executable, str(HERE / "alert_to_a2a.py"), "--payload", str(payload), "--out", str(out),
           "--state", str(a.state), "--breaker", str(a.breaker)]
    if a.limits:
        cmd += ["--limits", str(a.limits)]
    cmd += ["--max-requests", str(a.max_sends if a.send_url else 20)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            raise ValueError(f"exit {p.returncode}")
        res = json.loads(p.stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return 500, {"error": "intake failed"}  # details stay out of the response: the caller is not trusted
    res["sent"] = []
    if a.send_url:
        written = [r["file"] for r in res["results"] if r.get("outcome") == "request_written"]  # only THIS call's requests
        if enqueue is not None:  # server mode: answer Grafana now, send in the background (a slow agent must not make Grafana retry)
            res["queued"] = written[: a.max_sends]
            for name in res["queued"]:
                enqueue(out / name, out)
        else:
            for name in written[: a.max_sends]:
                res["sent"].append(send(out / name, out, a))
        res["deferred"] = [r["alert"] for r in res["results"] if r.get("outcome") == "deferred_over_cap"]  # not marked sent: Grafana re-delivers them
    return 200, res


def send(req: Path, out: Path, a: argparse.Namespace) -> dict:
    """Send ONE request to the gateway, save the receipt, record the outcome in the breaker. No retry here: the breaker owns that."""
    key = json.loads(req.read_text())["id"].removeprefix("ah-")
    headers = {"Content-Type": "application/json", "A2A-Version": "1.0"}
    tok = os.environ.get(a.send_token_env, "")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    status, retry_after, data = 0, None, b""
    try:
        with urllib.request.urlopen(urllib.request.Request(a.send_url, req.read_bytes(), headers), timeout=a.send_timeout) as r:
            status, data = r.status, r.read(8_000_000)
    except urllib.error.HTTPError as e:
        status, data = e.code, e.read(100_000)
        ra = e.headers.get("Retry-After")
        retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        data = json.dumps({"error": f"transport: {e}"}).encode()
    receipt = out / f"receipt-{req.stem}.json"
    body = None
    try:
        body = json.loads(data)
        receipt.write_bytes(data)
    except ValueError:
        receipt.write_text(json.dumps({"error": data[:400].decode("utf-8", "replace")}))
    timed_out = status == 0
    if timed_out:
        # The agent may still be running on the server and we do not know what it spends: stop ALL sending until a person looks.
        (a.breaker.parent / "guard-loop.disabled").write_text("send timed out or transport failed; remove after checking the agent\n")
    cmd = [sys.executable, str(HERE / "alert_to_a2a.py"), "--breaker", str(a.breaker), "--record", str(receipt), "--key", key]
    # kagent returns errors as HTTP 200 with the error in the body: then the status says nothing, so let the breaker read the message.
    if status and not (status == 200 and isinstance(body, dict) and (body.get("error") or "FAILED" in json.dumps((body.get("result") or {}).get("task", {}).get("status", {})))):
        cmd += ["--status", str(status)]
    if a.limits:
        cmd += ["--limits", str(a.limits)]
    if retry_after is not None:
        cmd += ["--retry-after", str(retry_after)]
    try:
        rec = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError):
        rec = subprocess.CompletedProcess(cmd, 1, "", "")
    if rec.returncode != 0:  # spend not counted: fail closed
        (a.breaker.parent / "guard-loop.disabled").write_text("breaker record failed; remove after checking\n")
        return {"request": req.name, "http": status, "receipt": receipt.name, "recorded": None, "kill_switch_set": True}
    return {"request": req.name, "http": status, "receipt": receipt.name, "recorded": json.loads(rec.stdout), "kill_switch_set": timed_out}


def start_sender(a: argparse.Namespace):
    """One background worker: sends run one at a time, in arrival order, under the same lock as intake (check-then-act)."""
    import queue
    import threading
    q: "queue.Queue[tuple[Path, Path]]" = queue.Queue(maxsize=20)

    def work():
        while True:
            req, out = q.get()
            with _LOCK:
                r = send(req, out, a)
            print(json.dumps({"sent": r}), flush=True)
            q.task_done()

    threading.Thread(target=work, daemon=True).start()

    def enqueue(req: Path, out: Path) -> None:
        try:
            q.put_nowait((req, out))
        except queue.Full:  # never block or grow without bound; a person sees it in the log and the outbox
            print(json.dumps({"dropped_queue_full": str(req)}), flush=True)
    return enqueue


def make_handler(a: argparse.Namespace, token: str, enqueue=None):
    class H(BaseHTTPRequestHandler):
        timeout = 10  # a client that stalls cannot hold the server

        def do_POST(self):  # noqa: N802
            try:
                n = int(self.headers.get("Content-Length", ""))
            except ValueError:
                n = -1
            if n < 0:
                return self._reply(411, {"error": "valid Content-Length required"})
            if n > MAX_BODY:
                return self._reply(413, {"error": "payload too large"})
            try:
                body = self.rfile.read(n)
            except OSError:
                return self._reply(408, {"error": "read timed out"})
            ok = hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}")
            with _LOCK:
                code, res = handle(body, a, ok, enqueue)
            self._reply(code, res)

        def _reply(self, code, res):
            data = json.dumps(res).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):  # no access log: payloads hold untrusted text
            pass

    return H


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", default="127.0.0.1:9094")
    ap.add_argument("--spool", type=Path, required=True)
    ap.add_argument("--outbox", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--breaker", type=Path, required=True)
    ap.add_argument("--limits", type=Path)
    ap.add_argument("--send-url", help="gateway A2A URL of the agent-health agent; omit to only write request files")
    ap.add_argument("--send-token-env", default="GATEWAY_TOKEN")
    ap.add_argument("--send-timeout", type=int, default=300)
    ap.add_argument("--max-sends", type=int, default=1)
    a = ap.parse_args()
    token = os.environ.get("ALERT_RECEIVER_TOKEN", "")
    if len(token) < 16:
        print("ALERT_RECEIVER_TOKEN (16+ chars) is required", file=sys.stderr)
        return 3
    host, port = a.listen.rsplit(":", 1)
    enqueue = start_sender(a) if a.send_url else None
    ThreadingHTTPServer((host, int(port)), make_handler(a, token, enqueue)).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
