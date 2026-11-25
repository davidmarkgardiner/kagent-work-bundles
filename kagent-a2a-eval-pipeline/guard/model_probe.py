#!/usr/bin/env python3
"""Model-route probe: one tiny request to an OpenAI-compatible route, classified in code. No agent, no loop.

Use it before the overseer is given work, and attach the result as evidence, so "the model route is down" is a verified fact in the ticket
and not a guess. It costs one token. Exit: 0 ok | 2 degraded (rate limited, 5xx, timeout, DNS or connection: a wait) | 1 refused (401, 403, 400, 404: needs a person) | 3 bad usage.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request


def probe(url: str, model: str, key: str | None, timeout: float) -> dict:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}).encode()
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    t0 = time.monotonic()
    out: dict = {"url": url, "model": model, "kind": None, "http": None, "retry_after_s": None, "detail": ""}
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=timeout)
        out.update(kind="ok", http=r.status)
    except urllib.error.HTTPError as e:
        out["http"] = e.code
        ra = e.headers.get("Retry-After")
        out["retry_after_s"] = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
        out["detail"] = e.read(300).decode("utf-8", "replace")
        out["kind"] = ("rate_limited" if e.code == 429 else "server_error" if e.code >= 500 else
                       "auth" if e.code in (401, 403) else "refused")
    except (socket.timeout, TimeoutError):
        out.update(kind="timeout", detail=f"no answer in {timeout}s")
    except urllib.error.URLError as e:
        reason = e.reason
        out.update(kind="timeout" if isinstance(reason, (socket.timeout, TimeoutError)) else
                   "dns" if isinstance(reason, socket.gaierror) else "connect", detail=str(reason)[:200])
    out["latency_ms"] = round((time.monotonic() - t0) * 1000)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="full chat-completions URL")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key-env", help="NAME of an environment variable holding the key (never the key itself)")
    ap.add_argument("--timeout", type=float, default=15)
    a = ap.parse_args()
    key = os.environ.get(a.api_key_env) if a.api_key_env else None
    if a.api_key_env and not key:
        print(json.dumps({"kind": "bad_usage", "detail": f"environment variable {a.api_key_env} is not set"}), file=sys.stderr)
        return 3
    r = probe(a.url, a.model, key, a.timeout)
    print(json.dumps(r))
    return {"ok": 0, "rate_limited": 2, "server_error": 2, "timeout": 2, "dns": 2, "connect": 2}.get(r["kind"], 1)


if __name__ == "__main__":
    sys.exit(main())
