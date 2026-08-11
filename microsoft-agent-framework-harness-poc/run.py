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

    if mode != "approve":
        raise ValueError("MODE must be request or approve")
    prior = json.loads(RUN_FILE.read_text()) if RUN_FILE.exists() else {}
    if prior.get("status") != "awaiting-approval":
        raise RuntimeError("refusing approval: no matching awaiting-approval request")

    client = OpenAIChatCompletionClient(
        model=os.environ["MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )
    agent = create_harness_agent(
        client=client,
        name="maf-harness-kagent-poc",
        agent_instructions=(
            "You are a safe POC orchestrator. Call invoke_kagent_prd exactly once "
            "with the supplied request. Do not use any other action. Then state that "
            "the request was handed to the kagent PRD specialist."
        ),
        tools=[invoke_kagent_prd],
        disable_web_search=True,
        disable_file_memory=False,
        file_memory_store=FileSystemAgentFileStore(STATE_DIR / "agent-file-memory"),
        loop_max_iterations=2,
    )
    session = agent.create_session(session_id="maf-harness-poc")
    response = await agent.run(f"Approved request: {request}", session=session)
    write_json(
        RUN_FILE,
        {
            "approval": "approved-by-lab-operator",
            "approved_at": timestamp(),
            "harness_response": response.text[:1200],
            "request": request,
            "status": "completed",
            "tool_invoked": ARTIFACT_FILE.exists(),
        },
    )
    print(f"HARNESS_APPROVAL_COMPLETED tool_invoked={ARTIFACT_FILE.exists()}")


if __name__ == "__main__":
    asyncio.run(main())
