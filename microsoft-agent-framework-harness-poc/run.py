"""Python-first Microsoft Agent Framework Harness POC entrypoint.

Modes are intentionally small and restartable: ``request`` records intent,
``deny`` terminally refuses it, ``approve`` performs one bounded A2A request,
and ``evaluate`` validates durable receipts.  A production factory must run one
such stage per short Argo task; it must not use a single long A2A chain.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agent_framework import FileSystemAgentFileStore, create_harness_agent
from agent_framework.openai import OpenAIChatCompletionClient

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


def getenv(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def runtime() -> tuple[ReceiptStore, RuntimeConfig]:
    state_dir = Path(getenv("STATE_DIR", "/state"))
    endpoint = getenv("KAGENT_A2A_URL")
    if not endpoint:
        endpoint = getenv("KAGENT_A2A_BASE_URL", "").rstrip("/") + "/debt-a2a-prd/"
    return ReceiptStore(state_dir), RuntimeConfig(state_dir=state_dir, endpoint=endpoint, trace_id=getenv("TRACE_ID"))


def configure_safe_observability() -> None:
    """Enable OTLP only when an approved collector endpoint is configured.

    Prompt, response, function-argument, and function-result capture remains
    disabled even when tracing is enabled.
    """
    if not getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers(enable_sensitive_data=False, enable_console_exporters=False)


def loop_should_continue(*, last_result, **kwargs):
    """Bound the experimental Harness loop to explicit completion markers only.

    The loop never repeats a side-effecting tool: ``invoke_once`` is idempotent
    and the tool returns the completion marker after its single durable receipt.
    """
    return "A2A_RECEIPT_RECORDED" not in (getattr(last_result, "text", "") or "")


def make_harness(tool):
    client = OpenAIChatCompletionClient(model=os.environ["MODEL"], api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ["OPENAI_BASE_URL"])
    return create_harness_agent(
        client=client,
        name="maf-python-kagent-coordinator",
        agent_instructions=("You are a bounded, approval-aware POC coordinator. "
                            "Call invoke_once exactly once. Once it returns its completion marker, stop. "
                            "Never claim remediation, do not invoke shell/Kubernetes/Git tools."),
        tools=[tool],
        disable_web_search=True,
        disable_file_memory=False,
        file_memory_store=FileSystemAgentFileStore(Path(getenv("STATE_DIR", "/state")) / "agent-file-memory"),
        loop_should_continue=loop_should_continue,
        loop_next_message="The required durable receipt is missing. Call invoke_once if it has not already completed.",
        loop_max_iterations=2,
    )


async def main() -> None:
    configure_safe_observability()
    mode = getenv("MODE", "request")
    request = getenv("POC_REQUEST", "Create a short educational PRD for a debt payoff calculator. No financial advice.")
    store, config = runtime()
    run_id = getenv("RUN_ID")

    if mode == "request":
        receipt = request_receipt(request, run_id or None)
        store.write(str(receipt["run_id"]), "request.json", receipt)
        print(f"HARNESS_REQUEST_RECORDED run_id={receipt['run_id']} status=awaiting-approval tool_invoked=false")
        return
    if not run_id:
        raise RuntimeError("RUN_ID is required after request mode")
    if mode == "deny":
        deny_request(store, run_id, request)
        print(f"HARNESS_DENIED run_id={run_id} tool_invoked=false")
        return
    if mode == "evaluate":
        result = evaluate_receipts(store, run_id)
        framework = await framework_local_evaluation(store, run_id)
        if result["result"] != "PASS" or framework["result"] != "PASS":
            raise RuntimeError("receipt evaluation failed")
        print(f"HARNESS_EVALUATION_PASS run_id={run_id}")
        return
    if mode != "approve":
        raise ValueError("MODE must be request, deny, approve, or evaluate")

    approved = approve_request(store, run_id, request)

    async def invoke_once(_: str) -> str:
        receipt = await invoke_a2a_once(config, store, approved, request)
        if receipt["outcome"] != "completed":
            raise RuntimeError(f"A2A stage blocked: {receipt.get('error_class', 'unknown_error')}")
        return "A2A_RECEIPT_RECORDED"

    agent = make_harness(invoke_once)
    session = agent.create_session(session_id=f"maf-{run_id}")
    await agent.run(f"Approved request {request}", session=session)
    receipt = store.read(run_id, "a2a-prd-attempt-1.json")
    if receipt.get("outcome") != "completed":
        raise RuntimeError("Harness completed without a successful terminal A2A receipt")
    store.write(run_id, "terminal.json", {**approved, "status": "completed", "tool_invoked": True})
    print(f"HARNESS_APPROVAL_COMPLETED run_id={run_id} tool_invoked=true")


if __name__ == "__main__":
    asyncio.run(main())
