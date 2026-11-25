#!/usr/bin/env python3
"""Send one question to a kagent agent over A2A, save the receipt, print a one-line summary.

--protocol 1x (default): kagent 1.x, SendMessage at <base>/<agent>, e.g. --base http://127.0.0.1:18083/agents/kagent.
--protocol 0.7: kagent 0.x including 0.9, message/send at <base>/<agent>/, e.g. --base http://127.0.0.1:18083/api/a2a/kagent.
The 0.x request and its reading are a2a_capture.py's own (build_payload, normalize), so they are tested once.

Demo helper. It waits (up to --wait seconds) only while kagent says the session is not ready yet
(KAGENT_SEND_NOT_ACCEPTED), which costs no model tokens. It never retries a failed run.
Exit: 0 completed | 1 failed or error | 3 bad usage.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a2a_shapes import summarize  # noqa: E402
import a2a_capture  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", required=True, help="A2A base URL, e.g. http://127.0.0.1:18083/agents/kagent")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", type=Path, required=True, help="where to save the receipt")
    ap.add_argument("--wait", type=int, default=180)
    ap.add_argument("--protocol", choices=["1x", "0.7"], default="1x", help="1x = kagent 1.x; 0.7 = kagent 0.x, including 0.9")
    a = ap.parse_args()
    if a.protocol == "0.7":
        return ask_0x(a)
    body = {"jsonrpc": "2.0", "id": f"demo-{a.agent}-{uuid.uuid4().hex[:8]}", "method": "SendMessage",
            "params": {"message": {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": [{"text": a.text}]}}}
    deadline, d = time.time() + a.wait, {}
    while True:
        req = urllib.request.Request(f"{a.base.rstrip('/')}/{a.agent}", json.dumps(body).encode(),
                                     {"content-type": "application/json", "A2A-Version": "1.0"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=300).read())
        except urllib.error.HTTPError as e:
            d = {"error": {"http": e.code, "body": e.read(400).decode("utf-8", "replace")}}
        except (urllib.error.URLError, TimeoutError) as e:
            d = {"error": {"transport": str(e)}}
        if "KAGENT_SEND_NOT_ACCEPTED" not in json.dumps(d) or time.time() > deadline:
            break
        time.sleep(3)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, indent=1))
    task = (d.get("result") or {}).get("task") or {}
    st = task.get("status") or {}
    text = " ".join(p.get("text", "") for p in (st.get("message") or {}).get("parts", []) if "text" in p)
    if not text:
        text = " ".join(p.get("text", "") for art in task.get("artifacts", []) for p in art.get("parts", []) if "text" in p)
    s = summarize(d) if task else {"tool_calls": [], "tokens_total": None}
    tools = [t["name"] for t in s.get("tool_calls", [])]
    print(json.dumps({"agent": a.agent, "state": st.get("state"), "tools": tools, "tokens": s.get("tokens_total"),
                      "answer": (text.strip() or json.dumps(d.get("error")))[:240]}))
    return 0 if st.get("state") == "TASK_STATE_COMPLETED" else 1


def ask_0x(a: argparse.Namespace) -> int:
    """kagent 0.x: one message/send. No waiting loop: 0.x has no 'session not ready' answer, and a send is never retried."""
    rid = f"demo-{a.agent}-{uuid.uuid4().hex[:8]}"   # unique: 0.x binds a contextId to the first agent that sees it
    req = urllib.request.Request(f"{a.base.rstrip('/')}/{a.agent}/", json.dumps(a2a_capture.build_payload(a.text, rid)).encode(),
                                 {"content-type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        d = {"error": {"http": e.code, "body": e.read(400).decode("utf-8", "replace")}}
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        d = {"error": {"transport": str(e)}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, indent=1))
    try:
        n = a2a_capture.normalize(d, rid)
        state, tools, text = n["a2a_state"], [t["name"] for t in n["tool_calls"]], n["final_response"] or n["outcome_reason"]
        ok = n["outcome"] == "completed"
    except a2a_capture.InfraError as exc:
        state, tools, text, ok = "error", [], str(exc), False
    print(json.dumps({"agent": a.agent, "state": str(state).upper(), "tools": tools, "tokens": summarize(d).get("tokens_total"),
                      "answer": text.strip()[:240]}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
