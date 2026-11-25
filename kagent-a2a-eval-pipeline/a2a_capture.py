#!/usr/bin/env python3
"""Send AgentEvalCase prompts to kagent agents over A2A (via agentgateway) and
capture normalized run files for the deterministic scorer.

Standard library plus PyYAML only. For every case and repeat this writes:

  <out>/runs/<case>.r<N>.run.json      normalized run (scorer input)
  <out>/receipts/<case>.r<N>.json      raw JSON-RPC response (evidence)
  <out>/rendered-cases/<case>.yaml     case after ${EVAL_*} substitution

Every run carries an ``outcome``:

  completed      agent answered; the scorer decides pass/fail
  agent_error    HTTP 200 but the task failed, carried kagent_error_code,
                 asked for input, or returned no text. Not scored as a pass.
  infra_error    transport, auth, routing or JSON-RPC protocol failure.
                 Says nothing about agent quality.

kagent reports application errors inside an HTTP 200 body, so the status code
alone is never trusted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

# Matches gateway/route-a2a-eval.yaml. Override with AGW_A2A_URL_TEMPLATE.
DEFAULT_URL_TEMPLATE = "{base}/a2a/{agent_ns}/{agent}/"
URL_TEMPLATE_1X = "{base}/agents/{agent_ns}/{agent}"   # kagent 1.x
USAGE_V1 = "https://kagent.dev/extensions/usage/v1"
SUBST_PATTERN = re.compile(r"\$\{(EVAL_[A-Z0-9_]+)\}")
# Only statuses where the gateway rejected the call before the agent ran.
# 502/504 are ambiguous (the agent may have started acting), so never retried.
RETRYABLE_HTTP = {429, 503}


class InfraError(Exception):
    pass


def render_case(text: str, env: dict[str, str]) -> str:
    """Substitute ${EVAL_*} tokens. Unknown tokens are an error, not blank."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in env:
            raise SystemExit(f"case references ${{{name}}} but it is not set")
        return env[name]

    return SUBST_PATTERN.sub(repl, text)


def new_traceparent() -> tuple[str, str]:
    trace_id = secrets.token_hex(16)
    return f"00-{trace_id}-{secrets.token_hex(8)}-01", trace_id


def build_payload(prompt: str, request_id: str) -> dict[str, Any]:
    # kagent needs kind + messageId on the message and kind:"text" on each part.
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": request_id,
                "contextId": f"ctx-{request_id}",
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
            }
        },
    }


def build_payload_1x(prompt: str, request_id: str) -> dict[str, Any]:
    """kagent 1.x: SendMessage, role ROLE_USER, bare text parts. No contextId: 1.x binds one to the first agent and rejects reuse."""
    return {"jsonrpc": "2.0", "id": request_id, "method": "SendMessage",
            "params": {"message": {"messageId": request_id, "role": "ROLE_USER", "parts": [{"text": prompt}]}}}


def normalize_1x(response: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Turn a kagent 1.x SendMessage response into the same shape as normalize(). Fails closed like it:
    only TASK_STATE_COMPLETED with a non-blank answer is a completed run."""
    if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
        raise InfraError("response is not a JSON-RPC 2.0 object")
    if request_id is not None and response.get("id") != request_id:
        raise InfraError(f"JSON-RPC id mismatch: sent {request_id!r}, got {response.get('id')!r}")
    if "error" in response:
        raise InfraError(f"JSON-RPC error: {json.dumps(response['error'])[:300]}")
    task = (response.get("result") or {}).get("task")
    if not isinstance(task, dict):
        raise InfraError("JSON-RPC response has no result.task object")
    status = task.get("status") or {}
    state = str(status.get("state", "unknown"))
    tool_calls: list[dict[str, Any]] = []
    tool_errors: list[str] = []
    seen: set[str] = set()
    texts: list[str] = []
    for art in task.get("artifacts") or []:
        for part in (art.get("parts") or []) if isinstance(art, dict) else []:
            if not isinstance(part, dict):
                continue
            kind = (part.get("metadata") or {}).get("kagent.dev/a2a/part-type")
            data = part.get("data")
            if isinstance(data, dict) and kind == "function_call":
                cid = str(data.get("id") or f"anon-{len(seen)}")
                if cid not in seen:
                    seen.add(cid)
                    args_ = data.get("args")
                    tool_calls.append({"id": cid, "name": data.get("name", ""), "arguments": args_ if isinstance(args_, dict) else {}})
            elif isinstance(data, dict) and kind == "function_response":
                resp = data.get("response")
                if data.get("isError") or data.get("error") or (isinstance(resp, dict) and (resp.get("isError") or resp.get("error"))):
                    tool_errors.append(str(data.get("name")))
            elif isinstance(part.get("text"), str) and data is None:
                texts.append(part["text"])
    msg_text = " ".join(p.get("text", "") for p in (status.get("message") or {}).get("parts", []) if isinstance(p, dict) and isinstance(p.get("text"), str))
    text = "\n".join(texts) if texts else ""
    usage = (task.get("metadata") or {}).get(USAGE_V1) or {}
    if state != "TASK_STATE_COMPLETED":
        outcome, reason, text = "agent_error", f"status.state={state}: {msg_text[:160]}".rstrip(": "), ""
    elif not text.strip():
        outcome, reason = "agent_error", "empty answer"
    else:
        outcome, reason = "completed", ""
    return {"outcome": outcome, "outcome_reason": reason, "a2a_state": state.replace("TASK_STATE_", "").lower(), "final_response": text,
            "tool_calls": tool_calls, "tool_errors": tool_errors, "trajectory_source": "a2a_artifacts",
            "input_tokens": usage.get("inputTokens"), "output_tokens": usage.get("outputTokens")}


def _never_sent(exc: urllib.error.URLError) -> bool:
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (ConnectionRefusedError, socket.gaierror))


def post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float, retries: int) -> dict[str, Any]:
    """POST once; retry only when the request provably never reached the agent.

    message/send is not idempotent: the agent may run tools. A timeout, reset or
    502/504 is ambiguous, so it becomes infra_error rather than a second call.
    """
    data = json.dumps(body).encode()
    last = "no attempt"
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(min(2 ** attempt, 20))
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in RETRYABLE_HTTP:
                continue
            raise InfraError(f"{last} (not retried)") from exc
        except urllib.error.URLError as exc:
            if _never_sent(exc):
                last = f"connect failed: {exc.reason}"
                continue
            raise InfraError(f"ambiguous transport failure, not retried: {exc.reason}") from exc
        except (TimeoutError, ConnectionError) as exc:
            raise InfraError(f"ambiguous transport failure after up to {timeout}s, not retried: {exc!r}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InfraError("non-JSON response body") from exc
    raise InfraError(f"{last} after {retries + 1} attempts")


def _texts(parts: list[Any]) -> list[str]:
    return [p["text"] for p in parts if isinstance(p, dict) and p.get("kind") == "text" and isinstance(p.get("text"), str)]


def normalize(response: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Turn a JSON-RPC message/send response into outcome, text, tools, usage.

    Fails closed: only status.state == "completed" with non-blank text and no
    kagent_error_code is a completed run.
    """
    if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
        raise InfraError("response is not a JSON-RPC 2.0 object")
    if request_id is not None and response.get("id") != request_id:
        raise InfraError(f"JSON-RPC id mismatch: sent {request_id!r}, got {response.get('id')!r}")
    if "error" in response:
        raise InfraError(f"JSON-RPC error: {json.dumps(response['error'])[:300]}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise InfraError("JSON-RPC response has no result object")

    history = result.get("history") or []
    state = (result.get("status") or {}).get("state", "unknown")
    error_code = None
    for msg in history:
        code = (msg.get("metadata") or {}).get("kagent_error_code") if isinstance(msg, dict) else None
        if code:
            error_code = code

    tool_calls: list[dict[str, Any]] = []
    tool_errors: list[str] = []
    seen: set[str] = set()
    for msg in history:
        if not isinstance(msg, dict) or msg.get("role") != "agent":
            continue
        for part in msg.get("parts") or []:
            if not isinstance(part, dict) or part.get("kind") != "data":
                continue
            meta = part.get("metadata") or {}
            event = meta.get("kagent_type") or meta.get("adk_type")
            data = part.get("data") or {}
            call_id = data.get("id") or f"anon-{len(seen)}"
            if event == "function_call" and call_id not in seen:
                seen.add(call_id)
                tool_calls.append({"id": call_id, "name": data.get("name", ""), "arguments": data.get("args") or {}})
            elif event == "function_response":
                resp = data.get("response")
                if data.get("isError") or data.get("error") or (isinstance(resp, dict) and resp.get("isError")):
                    tool_errors.append(str(data.get("name")))

    text = ""
    if not error_code:
        artifact_text = [t for a in result.get("artifacts") or [] if isinstance(a, dict) for t in _texts(a.get("parts") or [])]
        if artifact_text:
            text = "\n".join(artifact_text)
        else:
            agent_msgs = [m for m in history if isinstance(m, dict) and m.get("role") == "agent" and _texts(m.get("parts") or [])]
            if agent_msgs:
                text = "\n".join(_texts(agent_msgs[-1]["parts"]))

    usage = (result.get("metadata") or {}).get("kagent_usage_metadata") or {}

    if error_code:
        outcome, reason = "agent_error", f"kagent_error_code={error_code}"
    elif state != "completed":
        # failed, input-required, auth-required, working, unknown, missing...
        outcome, reason = "agent_error", f"status.state={state}"
    elif not text.strip():
        outcome, reason = "agent_error", "empty answer"
    else:
        outcome, reason = "completed", ""

    return {
        "outcome": outcome,
        "outcome_reason": reason,
        "a2a_state": state,
        "final_response": text,
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "trajectory_source": "a2a_history",
        "input_tokens": usage.get("promptTokenCount"),
        "output_tokens": usage.get("candidatesTokenCount"),
    }


def load_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = os.environ.get("AGW_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    extra = os.environ.get("AGW_EXTRA_HEADERS")
    if extra:
        headers.update({str(k): str(v) for k, v in json.loads(extra).items()})
    return headers


def select_cases(cases_dir: Path, tier: str | None, only: list[str]) -> list[Path]:
    paths = []
    for path in sorted(cases_dir.glob("*.yaml")):
        meta = (yaml.safe_load(path.read_text()) or {}).get("metadata", {})
        if only and meta.get("name") not in only:
            continue
        if tier and (meta.get("labels") or {}).get("tier", "full") != tier:
            continue
        paths.append(path)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base-url", default=os.environ.get("AGW_BASE_URL"), help="agentgateway base URL (env AGW_BASE_URL)")
    ap.add_argument("--protocol", choices=["0.7", "1x"], default=os.environ.get("AGW_A2A_PROTOCOL", "0.7"), help="kagent A2A protocol: 0.7 (message/send) or 1x (SendMessage)")
    ap.add_argument("--url-template", default=os.environ.get("AGW_A2A_URL_TEMPLATE"))
    ap.add_argument("--tier", help="only cases with metadata.labels.tier == TIER (default label: full)")
    ap.add_argument("--case", action="append", default=[], help="only this case name (repeatable)")
    ap.add_argument("--agent", help="only cases for this spec.agent (used by parallel:matrix)")
    ap.add_argument("--repeat", type=int, default=int(os.environ.get("EVAL_REPEAT", "1")))
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("EVAL_TIMEOUT_S", "180")))
    ap.add_argument("--retries", type=int, default=2, help="retries for connection errors and 429/502/503/504 only")
    ap.add_argument("--pause", type=float, default=float(os.environ.get("EVAL_PAUSE_S", "1")), help="seconds between calls")
    args = ap.parse_args()

    if not args.base_url:
        print("AGW_BASE_URL / --base-url is required", file=sys.stderr)
        return 3

    headers = load_headers()
    env = {k: v for k, v in os.environ.items() if k.startswith("EVAL_")}
    for sub in ("runs", "receipts", "rendered-cases"):
        (args.out / sub).mkdir(parents=True, exist_ok=True)

    cases = select_cases(args.cases_dir, args.tier, args.case)
    if not cases:
        print("no cases selected", file=sys.stderr)
        return 2

    pipeline_id = os.environ.get("CI_PIPELINE_ID", "local")
    counts = {"completed": 0, "agent_error": 0, "infra_error": 0}
    for path in cases:
        rendered = render_case(path.read_text(), env)
        case = yaml.safe_load(rendered)
        spec = case["spec"]
        if args.agent and spec["agent"] != args.agent:
            continue
        name = case["metadata"]["name"]
        (args.out / "rendered-cases" / f"{name}.yaml").write_text(rendered)
        case_sha = hashlib.sha256(rendered.encode()).hexdigest()
        agent_ns = spec["input"].get("agentNamespace", "kagent")
        url = (args.url_template or (URL_TEMPLATE_1X if args.protocol == "1x" else DEFAULT_URL_TEMPLATE)).format(base=args.base_url.rstrip("/"), agent_ns=agent_ns, agent=spec["agent"])
        if not url.endswith("/"):
            url += "/"  # kagent A2A returns 404 without the trailing slash

        for n in range(1, args.repeat + 1):
            # Unique per call: kagent binds a contextId (session) to the first agent
            # that used it, so a reused id returns 403 or leaks prior history.
            run_id = f"{pipeline_id}-{spec['agent']}-{name}-r{n}-{secrets.token_hex(4)}"
            traceparent, trace_id = new_traceparent()
            started = time.monotonic()
            receipt: dict[str, Any] = {}
            try:
                one_x = args.protocol == "1x"
                receipt = post_json(url, (build_payload_1x if one_x else build_payload)(spec["input"]["prompt"], run_id),
                                    {**headers, "traceparent": traceparent, **({"A2A-Version": "1.0"} if one_x else {})}, args.timeout, args.retries)
                norm = (normalize_1x if one_x else normalize)(receipt, run_id)
            except InfraError as exc:
                norm = {"outcome": "infra_error", "outcome_reason": str(exc), "a2a_state": None,
                        "final_response": "", "tool_calls": [], "tool_errors": [],
                        "trajectory_source": "none", "input_tokens": None, "output_tokens": None}
            latency_ms = int((time.monotonic() - started) * 1000)

            run = {"run_id": run_id, "case_id": name, "agent": spec["agent"], "repeat": n,
                   "case_sha256": case_sha, "commit_sha": os.environ.get("CI_COMMIT_SHA", "local"),
                   "trace_id": trace_id, "model": os.environ.get("EVAL_MODEL_LABEL", "{{MODEL_NAME}}"),
                   "latency_ms": latency_ms, "endpoint_path": url.split("://", 1)[-1].split("/", 1)[-1], **norm}
            stem = f"{name}.r{n}"
            (args.out / "runs" / f"{stem}.run.json").write_text(json.dumps(run, indent=2) + "\n")
            (args.out / "receipts" / f"{stem}.json").write_text(json.dumps(receipt, indent=2) + "\n")
            counts[norm["outcome"]] += 1
            tools = ",".join(c["name"] for c in norm["tool_calls"]) or "-"
            print(f"case={name} repeat={n} outcome={norm['outcome']} latency_ms={latency_ms} tools={tools} "
                  f"{norm['outcome_reason']}".rstrip())
            time.sleep(args.pause)

    print(f"captured completed={counts['completed']} agent_error={counts['agent_error']} infra_error={counts['infra_error']}")
    # Capture never fails the job on agent quality; score_and_gate.py decides.
    return 3 if counts["infra_error"] and not counts["completed"] and not counts["agent_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
