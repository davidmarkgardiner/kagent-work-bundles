"""Invoke the installed kagent 1.x Session API through grpcurl reflection."""
import json
import os
import re
import subprocess
import uuid


def rpc(method, payload, traceparent):
    command = [os.getenv("GRPCURL", "grpcurl"), "-plaintext", "-max-time", "120",
               "-max-msg-sz", "1048576", "-H", "x-user-id: " + os.getenv("KAGENT_USER_ID", "admin@kagent.dev"),
               "-H", "traceparent: " + traceparent, "-d", "@",
               os.getenv("KAGENT_GRPC_ADDRESS", "127.0.0.1:18083"), method]
    result = subprocess.run(command, input=json.dumps(payload), capture_output=True,
                            text=True, timeout=130, check=True)
    if len(result.stdout) > 1048576:
        raise ValueError("Agent response exceeded the receiver limit")
    return json.loads(result.stdout)


def terminal_text(response):
    task = response.get("task")
    if task is not None:
        if task.get("status", {}).get("state") != "TASK_STATE_COMPLETED":
            raise ValueError("Agent task did not complete")
        parts = [p for artifact in task.get("artifacts", []) for p in artifact.get("parts", [])]
    else:
        parts = response.get("message", {}).get("parts", [])
    text = " ".join(p["text"] for p in parts if isinstance(p.get("text"), str))[:3000]
    if not text:
        raise ValueError("Agent returned no terminal text")
    return text


def invoke_session(prompt, traceparent, invocation, on_session=None):
    namespace = os.getenv("AGENT_NAMESPACE", "kagent")
    agent = os.getenv("AGENT_NAME", "otel-substrate-reader")
    session = rpc("kagent.api.v1alpha1.SessionService/CreateSession", {
        "agent": {"namespace": namespace, "name": agent}, "requestId": str(uuid.uuid4())
    }, traceparent)["session"]
    session_id = session["id"]
    if not re.fullmatch(r"[a-f0-9-]{36}", session_id):
        raise ValueError("Invalid Session identity")
    invocation.update(sessionId=session_id, actorName="session-" + session_id)
    if on_session:
        on_session("session-" + session_id)
    response = rpc("lf.a2a.v1.A2AService/SendMessage", {
        "tenant": namespace + "/" + agent,
        "message": {"messageId": str(uuid.uuid4()), "contextId": session_id,
                    "role": "ROLE_USER", "parts": [{"text": prompt}]}
    }, traceparent)
    return terminal_text(response)
