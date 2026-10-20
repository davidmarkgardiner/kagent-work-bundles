"""Direct A2A 1.0 call to the standalone native kagent ADK service."""
import json
import urllib.request
import uuid
from substrate_call import terminal_text


def invoke_standalone(prompt, headers, invocation, url):
    context_id = str(uuid.uuid4())
    invocation["sessionId"] = context_id
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "SendMessage", "params": {
        "message": {"messageId": str(uuid.uuid4()), "contextId": context_id,
                    "role": "ROLE_USER", "parts": [{"text": prompt}]},
        "configuration": {"returnImmediately": False}}}
    request = urllib.request.Request(url, json.dumps(payload).encode(),
                                    {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError("Agent response exceeded receiver limit")
    result = json.loads(body)
    if "error" in result:
        raise ValueError("Standalone agent returned a JSON-RPC error")
    return terminal_text(result.get("result", {}))
