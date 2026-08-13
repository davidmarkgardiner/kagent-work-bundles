"""Bounded Python Harness runtime for the kagent A2A proof.

All mutable state is scoped to one immutable run ID.  The Harness has no
Kubernetes credentials; it can only make the fixed A2A request after an
operator-created approval record exists.  Any mutation remains an external
Argo Workflow which must produce its own terminal receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx


STAGE = "prd"
SAFE_EVENT_FIELDS = {"run_id", "stage", "attempt", "agent", "outcome", "error_class", "http_status", "latency_ms", "trace_id", "timestamp"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_error_class(exc: Exception | None = None, status: int | None = None) -> str:
    if status is not None:
        if status == 429:
            return "rate_limited"
        if 500 <= status <= 599:
            return "upstream_5xx"
        if status in {401, 403}:
            return "unauthorized"
        if status == 404:
            return "not_found"
        return "upstream_http_error"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.RequestError):
        return "transport_error"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "invalid_response"
    return "unknown_error"


@dataclass(frozen=True)
class RuntimeConfig:
    state_dir: Path
    endpoint: str
    agent: str = "debt-a2a-prd"
    trace_id: str = ""


class ReceiptStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir

    def path(self, run_id: str, name: str) -> Path:
        return self.state_dir / run_id / name

    def write(self, run_id: str, name: str, value: dict[str, Any]) -> Path:
        path = self.path(run_id, name)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        tmp.chmod(0o600)
        tmp.replace(path)
        return path

    def read(self, run_id: str, name: str) -> dict[str, Any]:
        return json.loads(self.path(run_id, name).read_text())


def request_receipt(request: str, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or str(uuid.uuid4())
    return {
        "schema_version": "maf-harness.v2",
        "run_id": run_id,
        "request_digest": canonical_digest(request),
        "status": "awaiting-approval",
        "tool_invoked": False,
        "timestamp": now(),
    }


def approve_request(store: ReceiptStore, run_id: str, request: str) -> dict[str, Any]:
    prior = store.read(run_id, "request.json")
    if prior.get("status") != "awaiting-approval":
        raise RuntimeError("approval requires an awaiting request")
    if prior.get("request_digest") != canonical_digest(request):
        raise RuntimeError("approval request digest does not match the recorded request")
    approved = {**prior, "status": "approved", "approved_at": now()}
    store.write(run_id, "approval.json", approved)
    return approved


def deny_request(store: ReceiptStore, run_id: str, request: str) -> dict[str, Any]:
    prior = store.read(run_id, "request.json")
    if prior.get("status") != "awaiting-approval" or prior.get("request_digest") != canonical_digest(request):
        raise RuntimeError("deny requires the matching awaiting request")
    denied = {**prior, "status": "DENIED", "tool_invoked": False, "denied_at": now()}
    store.write(run_id, "terminal.json", denied)
    return denied


def terminal_a2a_text(data: dict[str, Any]) -> str:
    if data.get("error"):
        return ""
    result = data.get("result") or {}
    if not isinstance(result, dict):
        return ""
    parts = result.get("parts") or []
    for artifact in result.get("artifacts") or []:
        if isinstance(artifact, dict):
            parts += artifact.get("parts") or []
    return "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("kind") == "text").strip()


async def invoke_a2a_once(config: RuntimeConfig, store: ReceiptStore, run: dict[str, Any], request: str, post: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Send exactly one message. Never retry ambiguous submissions automatically."""
    run_id = str(run["run_id"])
    receipt_name = f"a2a-{STAGE}-attempt-1.json"
    existing = store.path(run_id, receipt_name)
    if existing.exists():
        return store.read(run_id, receipt_name)
    if run.get("status") != "approved" or run.get("request_digest") != canonical_digest(request):
        raise RuntimeError("A2A call requires matching approved state")
    message_id = f"maf-{run_id}-{STAGE}-attempt-1"
    payload = {"jsonrpc": "2.0", "id": message_id, "method": "message/send", "params": {"message": {"kind": "message", "messageId": message_id, "contextId": message_id, "role": "user", "parts": [{"kind": "text", "text": request}]}}}
    start = time.monotonic()
    try:
        if post is None:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(config.endpoint, json=payload)
        else:
            response = await post(config.endpoint, payload)
        status = int(response.status_code)
        data = response.json()
        text = terminal_a2a_text(data)
        if status != 200 or not text:
            raise A2AResponseError(status, "missing terminal A2A result")
        receipt = {"run_id": run_id, "request_digest": run["request_digest"], "stage": STAGE, "attempt": 1, "agent": config.agent, "outcome": "completed", "http_status": status, "latency_ms": round((time.monotonic() - start) * 1000), "terminal_text_present": True, "trace_id": config.trace_id, "timestamp": now()}
    except Exception as exc:  # receipt is mandatory even when transport/JSON fails
        status = exc.status if isinstance(exc, A2AResponseError) else None
        receipt = {"run_id": run_id, "request_digest": run["request_digest"], "stage": STAGE, "attempt": 1, "agent": config.agent, "outcome": "BLOCKED", "http_status": status, "latency_ms": round((time.monotonic() - start) * 1000), "error_class": safe_error_class(exc, status), "trace_id": config.trace_id, "timestamp": now()}
    store.write(run_id, receipt_name, receipt)
    return receipt


class A2AResponseError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def evaluate_receipts(store: ReceiptStore, run_id: str) -> dict[str, Any]:
    """Deterministic evidence gate. Semantic/LLM evaluation cannot override it."""
    criteria: list[dict[str, Any]] = []
    def check(code: str, value: bool) -> None:
        criteria.append({"code": code, "passed": value})
    try:
        request = store.read(run_id, "request.json")
        approval = store.read(run_id, "approval.json")
        a2a = store.read(run_id, f"a2a-{STAGE}-attempt-1.json")
        check("request_schema_and_run_id", request.get("run_id") == run_id and request.get("schema_version") == "maf-harness.v2")
        check("approval_bound_to_request", approval.get("run_id") == run_id and approval.get("request_digest") == request.get("request_digest") and approval.get("status") == "approved")
        check("exactly_one_terminal_a2a_receipt", a2a.get("run_id") == run_id and a2a.get("request_digest") == request.get("request_digest") and a2a.get("attempt") == 1 and a2a.get("outcome") == "completed" and a2a.get("terminal_text_present") is True)
    except (OSError, ValueError, KeyError):
        check("receipts_readable", False)
    result = {"kind": "maf-harness-deterministic-evaluation", "run_id": run_id, "result": "PASS" if criteria and all(item["passed"] for item in criteria) else "FAIL", "criteria": criteria, "timestamp": now()}
    store.write(run_id, "evaluation.json", result)
    return result


async def framework_local_evaluation(store: ReceiptStore, run_id: str) -> dict[str, Any]:
    """Use Agent Framework's local evaluator as a second, API-free assertion."""
    deterministic = evaluate_receipts(store, run_id)
    try:
        from agent_framework import EvalItem, LocalEvaluator, Message, evaluator

        @evaluator(name="deterministic_receipt_gate")
        def receipt_gate(response: str) -> dict[str, Any]:
            passed = '"result": "PASS"' in response
            return {"passed": passed, "reason": "deterministic receipt gate must pass"}

        item = EvalItem(conversation=[Message(role="user", contents=["Evaluate the receipt chain."]), Message(role="assistant", contents=[json.dumps(deterministic)])])
        result = await LocalEvaluator(receipt_gate).evaluate([item], eval_name="maf-receipt-gate")
        passed = bool(result.items[0].is_passed)
        framework = {"kind": "agent-framework-local-evaluation", "run_id": run_id, "result": "PASS" if passed else "FAIL", "timestamp": now()}
    except Exception as exc:
        # The exception text may contain a model prompt or tool data; retain
        # only its safe class in the durable receipt.
        framework = {"kind": "agent-framework-local-evaluation", "run_id": run_id, "result": "FAIL", "error_class": safe_error_class(exc), "timestamp": now()}
    store.write(run_id, "framework-evaluation.json", framework)
    return framework
