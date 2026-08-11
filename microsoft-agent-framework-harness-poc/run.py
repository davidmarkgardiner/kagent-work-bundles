"""Small, evidence-first Harness Agent proof.

The request phase deliberately cannot call a tool. The approval phase uses a
Microsoft Agent Framework Harness Agent and one safe function tool to invoke a
read-only kagent PRD worker through the in-cluster A2A endpoint.
"""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from agent_framework import FileSystemAgentFileStore, create_harness_agent
from agent_framework.openai import OpenAIChatCompletionClient


STATE_DIR = Path(os.getenv("STATE_DIR", "/state"))
RUN_FILE = STATE_DIR / "harness-run.json"
ARTIFACT_FILE = STATE_DIR / "harness-artifact.json"
FACTORY_FILE = STATE_DIR / "factory-run.json"


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


async def invoke_kagent_prd(request: str) -> str:
    """Invoke the lab's read-only kagent PRD specialist for the supplied request.

    This tool only calls the fixed in-cluster A2A endpoint. It has no Kubernetes
    credentials, no GitLab token, and no write-capable MCP tools.
    """
    endpoint = os.environ["KAGENT_A2A_URL"]
    message_id = "maf-harness-approved-prd"
    payload = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": message_id,
                "contextId": "maf-harness-poc",
                "role": "user",
                "parts": [{"kind": "text", "text": request}],
            }
        },
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        data = response.json()
    result = data.get("result", {})
    parts = result.get("artifacts", [{}])[0].get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts if part.get("kind") == "text")
    write_json(
        ARTIFACT_FILE,
        {
            "a2a_endpoint": endpoint,
            "a2a_http_status": response.status_code,
            "a2a_result_present": bool(result),
            "kagent_response_excerpt": text[:1200],
            "timestamp": timestamp(),
        },
    )
    return "kagent PRD specialist completed; durable A2A receipt recorded in /state/harness-artifact.json"


def extract_a2a_text(data: dict) -> str:
    """Extract terminal artifact text without relying on provider-specific fields."""
    result = data.get("result", {})
    parts = []
    for artifact in result.get("artifacts", []):
        parts.extend(artifact.get("parts", []))
    if not parts:
        parts = result.get("parts", [])
    return "\n".join(part.get("text", "") for part in parts if part.get("kind") == "text")


async def call_sdlc_specialist(agent_name: str, stage: str, prompt: str) -> str:
    """Call one fixed, tool-free kagent SDLC specialist over A2A."""
    endpoint = f"{os.environ['KAGENT_A2A_BASE_URL'].rstrip('/')}/{agent_name}/"
    message_id = f"maf-sdlc-{stage}"
    payload = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": message_id,
                # kagent stores A2A context per agent. Do not reuse a context ID
                # across specialists: it can bind a later request to another
                # agent's execution history.
                "contextId": f"maf-harness-sdlc-factory-{stage}",
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
            }
        },
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        data = response.json()
    text = extract_a2a_text(data)
    write_json(
        STATE_DIR / f"a2a-{stage}-receipt.json",
        {
            "agent": agent_name,
            "endpoint": endpoint,
            "http_status": response.status_code,
            "result_error": data.get("result", {}).get("status", {}).get("message"),
            "result_state": data.get("result", {}).get("status", {}).get("state"),
            "terminal_text_present": bool(text),
            "timestamp": timestamp(),
        },
    )
    if not text:
        raise RuntimeError(f"{stage} returned no terminal text artifact")
    return text


async def run_full_sdlc_factory(request: str) -> str:
    """Run plan, build, test, docs, and independent evaluation in that order.

    Every stage is a fixed tool-free kagent Agent. This coordinator persists a
    receipt after each handoff and stops at the first missing stage artifact.
    """
    stages = [
        ("plan", "maf-sdlc-plan", request),
        ("build", "maf-sdlc-build", "Use this plan to produce the build artifact:\n{plan}"),
        ("test", "maf-sdlc-test", "Use these artifacts to define tests:\nPLAN:\n{plan}\nBUILD:\n{build}"),
        ("document", "maf-sdlc-document", "Use these artifacts to define documentation:\nPLAN:\n{plan}\nBUILD:\n{build}"),
        ("evaluate", "maf-sdlc-evaluator", "Independently evaluate this evidence:\nPLAN:\n{plan}\nBUILD:\n{build}\nTEST:\n{test}\nDOCS:\n{document}"),
    ]
    artifacts: dict[str, str] = {}
    for stage, agent_name, template in stages:
        prompt = template.format(**artifacts) if artifacts else template
        # Bound stage payloads, preserving only enough evidence for the next role.
        prompt = prompt[:3000]
        output = await call_sdlc_specialist(agent_name, stage, prompt)
        artifacts[stage] = output[:1200]
        write_json(
            FACTORY_FILE,
            {
                "completed_stages": list(artifacts),
                "request": request,
                "stage_artifacts": artifacts,
                "status": "running" if stage != "evaluate" else "evaluated",
                "timestamp": timestamp(),
            },
        )
    evaluation = artifacts["evaluate"].upper()
    if "EVALUATION: PASS" not in evaluation:
        raise RuntimeError("independent evaluator did not return EVALUATION: PASS")
    return "SDLC factory completed: plan, build, test, document, evaluate; receipts persisted in /state/factory-run.json"


def make_harness(name: str, instructions: str, tools: list):
    client = OpenAIChatCompletionClient(
        model=os.environ["MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )
    return create_harness_agent(
        client=client,
        name=name,
        agent_instructions=instructions,
        tools=tools,
        disable_web_search=True,
        disable_file_memory=False,
        file_memory_store=FileSystemAgentFileStore(STATE_DIR / "agent-file-memory"),
        loop_max_iterations=2,
    )


async def main() -> None:
    mode = os.getenv("MODE", "request")
    request = os.getenv(
        "POC_REQUEST",
        "Create a short educational PRD for a debt payoff calculator. No financial advice.",
    )
    if mode == "request":
        write_json(
            RUN_FILE,
            {
                "approval": "required",
                "created_at": timestamp(),
                "request": request,
                "status": "awaiting-approval",
                "tool_invoked": False,
            },
        )
        print("HARNESS_REQUEST_RECORDED status=awaiting-approval tool_invoked=false")
        return

    prior = json.loads(RUN_FILE.read_text()) if RUN_FILE.exists() else {}
    if mode == "approve":
        if prior.get("status") != "awaiting-approval":
            raise RuntimeError("refusing approval: no matching awaiting-approval request")
        agent = make_harness(
            "maf-harness-kagent-poc",
            "You are a safe POC orchestrator. Call invoke_kagent_prd exactly once "
            "with the supplied request. Do not use any other action.",
            [invoke_kagent_prd],
        )
        session = agent.create_session(session_id="maf-harness-poc")
        response = await agent.run(f"Approved request: {request}", session=session)
        write_json(RUN_FILE, {"approval": "approved-by-lab-operator", "approved_at": timestamp(), "harness_response": response.text[:1200], "request": request, "status": "completed", "tool_invoked": ARTIFACT_FILE.exists()})
        print(f"HARNESS_APPROVAL_COMPLETED tool_invoked={ARTIFACT_FILE.exists()}")
        return

    if mode == "factory":
        if prior.get("status") != "completed" or not ARTIFACT_FILE.exists():
            raise RuntimeError("refusing factory run: prior approval and A2A receipt are required")
        agent = make_harness(
            "maf-harness-sdlc-factory",
            "You are the SDLC factory coordinator. Call run_full_sdlc_factory exactly "
            "once with the supplied request. Do not perform any other action.",
            [run_full_sdlc_factory],
        )
        session = agent.create_session(session_id="maf-harness-sdlc-factory")
        response = await agent.run(f"Approved SDLC request: {request}", session=session)
        factory = json.loads(FACTORY_FILE.read_text()) if FACTORY_FILE.exists() else {}
        if factory.get("status") != "evaluated":
            raise RuntimeError("factory did not persist evaluated stage state")
        print(f"HARNESS_SDLC_FACTORY_COMPLETED stages={','.join(factory.get('completed_stages', []))}")
        return

    raise ValueError("MODE must be request, approve, or factory")


if __name__ == "__main__":
    asyncio.run(main())
