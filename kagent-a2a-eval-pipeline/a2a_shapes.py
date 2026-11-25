"""Normalise a kagent A2A task receipt (0.7.x or 1.x / A2A 1.0) into the facts the Warden emitter
and the Guard detector need. Unknown values stay None: callers must treat None as 'no coverage',
never as zero."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

USAGE_V1 = "https://kagent.dev/extensions/usage/v1"
PART_V1 = "kagent.dev/a2a/part-type"


def _ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def summarize(receipt: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"version": None, "state": None, "completed": False, "error_code": None, "tool_calls": [],
                           "tokens_in": None, "tokens_out": None, "tokens_total": None,
                           "started": None, "finished": None, "duration_s": None, "max_tool_output_chars": None}
    result = receipt.get("result") if isinstance(receipt, dict) else None
    if not isinstance(result, dict):
        return out
    if isinstance(result.get("task"), dict):
        t = result["task"]
        out["version"] = "1.x"
        out["state"] = (t.get("status") or {}).get("state")
        out["completed"] = out["state"] == "TASK_STATE_COMPLETED"
        parts = [p for a in t.get("artifacts") or [] if isinstance(a, dict) for p in a.get("parts") or [] if isinstance(p, dict)]
        kind = lambda p: (p.get("metadata") or {}).get(PART_V1)
        meta = t.get("metadata") or {}
        usage = meta.get(USAGE_V1) or {}
        out["tokens_in"], out["tokens_out"], out["tokens_total"] = _int(usage.get("inputTokens")), _int(usage.get("outputTokens")), _int(usage.get("totalTokens"))
        out["started"] = meta.get("kagent.dev/a2a/task-created-at")
        out["finished"] = (t.get("status") or {}).get("timestamp")
    else:
        out["version"] = "0.7"
        out["state"] = (result.get("status") or {}).get("state")
        out["completed"] = out["state"] == "completed"
        hist = [m for m in result.get("history") or [] if isinstance(m, dict)]
        parts = [p for m in hist if m.get("role") == "agent" for p in m.get("parts") or [] if isinstance(p, dict)]
        kind = lambda p: (p.get("metadata") or {}).get("kagent_type") or (p.get("metadata") or {}).get("adk_type")
        out["error_code"] = next((c for c in ((m.get("metadata") or {}).get("kagent_error_code") for m in hist) if c), None)
        usage = (result.get("metadata") or {}).get("kagent_usage_metadata") or {}
        out["tokens_in"], out["tokens_out"], out["tokens_total"] = _int(usage.get("promptTokenCount")), _int(usage.get("candidatesTokenCount")), _int(usage.get("totalTokenCount"))
        out["finished"] = (result.get("status") or {}).get("timestamp")
    seen: set[str] = set()
    for p in parts:
        d = p.get("data")
        if kind(p) == "function_call" and isinstance(d, dict):
            cid = str(d.get("id") or f"anon{len(seen)}")
            if cid not in seen:
                seen.add(cid)
                out["tool_calls"].append({"id": cid, "name": str(d.get("name") or "")})
    sizes = [len(json.dumps(p["data"].get("response"))) for p in parts
             if kind(p) == "function_response" and isinstance(p.get("data"), dict)]
    out["max_tool_output_chars"] = max(sizes) if sizes else None
    a, b = _ts(out["started"]), _ts(out["finished"])
    if a and b and b >= a:
        out["duration_s"] = round((b - a).total_seconds(), 3)
    return out
