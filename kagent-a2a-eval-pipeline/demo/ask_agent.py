#!/usr/bin/env python3
"""Send one question to a kagent 1.x agent over A2A, save the receipt, print a one-line summary.

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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", required=True, help="A2A base URL, e.g. http://127.0.0.1:18083/agents/kagent")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", type=Path, required=True, help="where to save the receipt")
    ap.add_argument("--wait", type=int, default=180)
    a = ap.parse_args()
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


if __name__ == "__main__":
    sys.exit(main())
