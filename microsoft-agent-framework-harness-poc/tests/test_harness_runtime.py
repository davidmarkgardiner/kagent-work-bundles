import asyncio

import httpx
import pytest

from harness_runtime import (
    ReceiptStore,
    RuntimeConfig,
    approve_request,
    deny_request,
    evaluate_receipts,
    framework_local_evaluation,
    invoke_a2a_once,
    request_receipt,
)


def request(store, text="safe request", run_id="run-1"):
    receipt = request_receipt(text, run_id)
    store.write(run_id, "request.json", receipt)
    return receipt


def test_request_and_deny_never_create_a2a_receipt(tmp_path):
    store = ReceiptStore(tmp_path)
    receipt = request(store)
    denied = deny_request(store, "run-1", "safe request")
    assert receipt["request_digest"] == denied["request_digest"]
    assert denied["status"] == "DENIED"
    assert not store.path("run-1", "a2a-prd-attempt-1.json").exists()


def test_approval_requires_exact_recorded_request(tmp_path):
    store = ReceiptStore(tmp_path)
    request(store)
    with pytest.raises(RuntimeError, match="digest"):
        approve_request(store, "run-1", "different request")
    assert not store.path("run-1", "approval.json").exists()


def test_successful_a2a_receipt_is_redacted_and_idempotent(tmp_path):
    store = ReceiptStore(tmp_path)
    request(store)
    approved = approve_request(store, "run-1", "safe request")
    calls = []

    async def post(endpoint, payload):
        calls.append((endpoint, payload))
        return httpx.Response(200, json={"result": {"artifacts": [{"parts": [{"kind": "text", "text": "super-secret output"}]}]}})

    config = RuntimeConfig(tmp_path, "https://example.invalid/a2a", trace_id="trace-1")
    receipt = asyncio.run(invoke_a2a_once(config, store, approved, "safe request", post))
    repeated = asyncio.run(invoke_a2a_once(config, store, approved, "safe request", post))
    saved = store.path("run-1", "a2a-prd-attempt-1.json").read_text()
    assert len(calls) == 1
    assert receipt == repeated
    assert receipt["outcome"] == "completed"
    assert "super-secret" not in saved
    assert calls[0][1]["params"]["message"]["messageId"].startswith("maf-run-1-prd-attempt-1")


@pytest.mark.parametrize("response", [httpx.Response(500, json={}), httpx.Response(200, json={"result": {}})])
def test_failure_always_persists_blocked_receipt(tmp_path, response):
    store = ReceiptStore(tmp_path)
    request(store)
    approved = approve_request(store, "run-1", "safe request")

    async def post(endpoint, payload):
        return response

    receipt = asyncio.run(invoke_a2a_once(RuntimeConfig(tmp_path, "https://example.invalid"), store, approved, "safe request", post))
    assert receipt["outcome"] == "BLOCKED"
    assert store.path("run-1", "a2a-prd-attempt-1.json").exists()


def test_deterministic_evaluation_fails_for_stale_or_failed_receipt(tmp_path):
    store = ReceiptStore(tmp_path)
    request(store)
    approved = approve_request(store, "run-1", "safe request")
    store.write("run-1", "a2a-prd-attempt-1.json", {"run_id": "other-run", "request_digest": approved["request_digest"], "stage": "prd", "attempt": 1, "outcome": "completed", "terminal_text_present": True})
    assert evaluate_receipts(store, "run-1")["result"] == "FAIL"


def test_deterministic_evaluation_passes_only_complete_bound_receipts(tmp_path):
    store = ReceiptStore(tmp_path)
    request(store)
    approved = approve_request(store, "run-1", "safe request")
    store.write("run-1", "a2a-prd-attempt-1.json", {"run_id": "run-1", "request_digest": approved["request_digest"], "stage": "prd", "attempt": 1, "outcome": "completed", "terminal_text_present": True})
    result = evaluate_receipts(store, "run-1")
    assert result["result"] == "PASS"
    assert all(criterion["passed"] for criterion in result["criteria"])


def test_agent_framework_local_evaluator_passes_valid_receipts(tmp_path):
    store = ReceiptStore(tmp_path)
    request(store)
    approved = approve_request(store, "run-1", "safe request")
    store.write("run-1", "a2a-prd-attempt-1.json", {"run_id": "run-1", "request_digest": approved["request_digest"], "stage": "prd", "attempt": 1, "outcome": "completed", "terminal_text_present": True})
    assert asyncio.run(framework_local_evaluation(store, "run-1"))["result"] == "PASS"
