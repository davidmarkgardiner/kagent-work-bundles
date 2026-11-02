"""Bounded fixture MCP tools and an explicitly simulated OpenAI-compatible model."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import time
import urllib.request
import uuid

TOOLS = {
    "get_inventory_status": ("Read the simulated inventory workload status.", {"readyReplicas": 1, "desiredReplicas": 1, "status": "healthy"}),
    "get_recent_alerts": ("Read simulated inventory alerts.", {"alerts": [], "source": "fixture"}),
    "review_change": ("Read the simulated deployment change review. Does not deploy.", {"change": "demo-release", "decision": "human_review_required", "mutatedResources": 0}),
    "check_dependency": ("Exercise a simulated unavailable dependency. Returns an intentional tool error.", {"dependency": "demo-stock", "status": "unavailable", "simulatedFailure": True}),
}
TOOLS.update({
    "get_kubernetes_workloads": ("Read simulated Kubernetes workload conditions.", {"namespace": "demo", "workload": "inventory", "readyReplicas": 0, "reason": "ImagePullBackOff"}),
    "query_grafana_alerts": ("Read simulated Grafana alerts and error-rate summary.", {"alert": "InventoryUnavailable", "state": "firing", "errorRate": "fixture 18%"}),
    "get_gitlab_issue": ("Read a simulated GitLab incident issue. Does not create an issue.", {"issue": "DEMO-42", "title": "Inventory rollout investigation", "state": "opened"}),
    "get_gitlab_pipeline": ("Read simulated GitLab pipeline status. Does not trigger a pipeline.", {"pipeline": "demo-pipeline", "status": "failed", "stage": "image-validation"}),
    "read_team_a_resource": ("Exercise a simulated allow decision for agent A and team A.", {"subjectAlias": "agent-a", "resourceAlias": "team-a", "decision": "allow"}),
    "attempt_cross_team_resource": ("Exercise a simulated deny decision for agent A and team B. No real identity token is used.", {"subjectAlias": "agent-a", "resourceAlias": "team-b", "decision": "deny"}),
    "read_team_b_resource": ("Exercise a simulated allow decision for agent B and team B.", {"subjectAlias": "agent-b", "resourceAlias": "team-b", "decision": "allow"}),
})
TOOL_SYSTEMS = {
    "get_kubernetes_workloads": "Kubernetes MCP", "query_grafana_alerts": "Grafana MCP",
    "get_gitlab_issue": "GitLab MCP", "get_gitlab_pipeline": "GitLab MCP",
    "read_team_a_resource": "Identity policy", "attempt_cross_team_resource": "Identity policy", "read_team_b_resource": "Identity policy",
}
WORKFLOWS = {
    "triage": ["get_kubernetes_workloads", "query_grafana_alerts", "get_gitlab_issue"],
    "sdlc": ["get_gitlab_issue", "get_gitlab_pipeline", "review_change"],
    "identity-isolation": ["read_team_a_resource", "attempt_cross_team_resource", "read_team_b_resource"],
    "inventory": ["get_inventory_status", "get_recent_alerts"],
    "change-review": ["get_inventory_status", "review_change"],
    "dependency-failure": ["check_dependency"],
}


def export_event(service, trace, span, parent, name, start, status, values, kind=2):
    attributes = [{"key": k, "value": {"boolValue": v} if isinstance(v, bool) else
                   {"intValue": str(v)} if isinstance(v, int) else {"stringValue": str(v)}}
                  for k, v in values.items()]
    resource = {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]}
    end = str(time.time_ns())
    records = {
        "traces": {"resourceSpans": [{"resource": resource, "scopeSpans": [{"spans": [{
            "traceId": trace, "spanId": span, "parentSpanId": parent, "name": name,
            "kind": kind, "startTimeUnixNano": str(start), "endTimeUnixNano": end,
            "status": {"code": status}, "attributes": attributes}]}]}]},
        "logs": {"resourceLogs": [{"resource": resource, "scopeLogs": [{"logRecords": [{
            "timeUnixNano": end, "traceId": trace, "spanId": span,
            "severityNumber": 17 if status == 2 else 9, "eventName": "demo.workflow.operation",
            "attributes": attributes}]}]}]},
    }
    delivered = True
    for signal, payload in records.items():
        try:
            request = urllib.request.Request(os.environ["OTEL_HTTP_ENDPOINT"] + "/v1/" + signal,
                                             json.dumps(payload).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read(1024)
        except (OSError, KeyError):
            delivered = False
            print("OTel export failed", flush=True)
    return delivered


def model_reply(payload):
    messages = payload.get("messages", [])
    user = " ".join(str(m.get("content", "")) for m in messages if m.get("role") == "user")
    workflow = next((key for key in WORKFLOWS if "DEMO_WORKFLOW=" + key in user), "inventory")
    completed = {call.get("function", {}).get("name") for message in messages
                 for call in message.get("tool_calls", [])}
    available = {tool.get("function", {}).get("name") for tool in payload.get("tools", [])}
    remaining = [name for name in WORKFLOWS[workflow] if name not in completed and name in available]
    if remaining:
        return {"role": "assistant", "content": None, "tool_calls": [{"id": "call_" + uuid.uuid4().hex[:16],
                "type": "function", "function": {"name": remaining[0], "arguments": "{}"}}]}, "tool_calls"
    return {"role": "assistant", "content": "SIMULATED_WORKFLOW_COMPLETE · " + workflow +
            ". Fixture model and fixture tool data. No cluster resources were changed."}, "stop"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply(200 if self.path == "/healthz" else 405, {"status": "fixture", "simulated": True})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 1048576:
                return self.reply(413, {"error": "Invalid request size"})
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected an object")
        except (ValueError, OSError):
            return self.reply(400, {"error": "Invalid JSON request"})
        start = time.time_ns()
        carrier = self.headers.get("traceparent", "")
        match = re.fullmatch(r"00-([a-f0-9]{32})-([a-f0-9]{16})-[a-f0-9]{2}", carrier)
        trace, parent = match.groups() if match else (uuid.uuid4().hex, "")
        span = uuid.uuid4().hex[:16]
        values = {"flow.simulated": True, "flow.component": "mcp", "http.request.method": "POST"}
        status, service, operation = 1, "flow-demo-tools", "MCP request"
        try:
            if self.path == "/mcp":
                method = payload.get("method")
                operation = "MCP " + str(method)
                if method == "initialize":
                    result = {"protocolVersion": payload.get("params", {}).get("protocolVersion", "2025-03-26"),
                              "capabilities": {"tools": {}}, "serverInfo": {"name": "simulated-workflow-tools", "version": "1.0.0"}}
                elif method == "tools/list":
                    result = {"tools": [{"name": name, "description": description,
                               "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}
                               for name, (description, _) in TOOLS.items()]}
                elif method == "tools/call":
                    name = payload.get("params", {}).get("name")
                    if name not in TOOLS or payload.get("params", {}).get("arguments", {}) not in ({}, None):
                        return self.reply(400, {"error": "Unknown fixture tool or arguments"})
                    time.sleep(0.35)
                    failed = name in {"check_dependency", "attempt_cross_team_resource"}
                    status = 2 if failed else 1
                    operation = "execute_tool " + name
                    values.update({"gen_ai.tool.name": name, "flow.workflow": name,
                                   "flow.result": "simulated_failure" if failed else "fixture_success"})
                    values["flow.tool.system"] = TOOL_SYSTEMS.get(name, "Workflow MCP")
                    if "subjectAlias" in TOOLS[name][1]:
                        access = TOOLS[name][1]
                        values.update({"flow.security.subject": access["subjectAlias"], "flow.security.resource": access["resourceAlias"],
                                       "flow.security.decision": access["decision"], "flow.security.authority": "simulated-policy"})
                    result = {"content": [{"type": "text", "text": json.dumps({"simulated": True, **TOOLS[name][1]})}],
                              "isError": failed}
                elif str(method).startswith("notifications/"):
                    return self.reply(202, {})
                elif method == "ping":
                    result = {}
                else:
                    return self.reply(200, {"jsonrpc": "2.0", "id": payload.get("id"),
                                            "error": {"code": -32601, "message": "Method not found"}})
                self.reply(200, {"jsonrpc": "2.0", "id": payload.get("id"), "result": result})
            elif self.path == "/v1/chat/completions":
                service, operation = "flow-fixture-model", "fixture chat completion"
                values["flow.component"] = "model"
                message, reason = model_reply(payload)
                model = str(payload.get("model", "fixture-workflow"))[:128]
                values["gen_ai.request.model"] = model
                identity = "chatcmpl-" + uuid.uuid4().hex
                common = {"id": identity, "created": int(time.time()), "model": model}
                if payload.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    delta = dict(message)
                    if "tool_calls" in delta:
                        delta["tool_calls"] = [dict(call, index=n) for n, call in enumerate(delta["tool_calls"])]
                    for data in [{**common, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                                 {**common, "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": reason}]}]:
                        self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                else:
                    self.reply(200, {**common, "object": "chat.completion", "choices": [{"index": 0, "message": message, "finish_reason": reason}]})
            else:
                status = 2
                self.reply(404, {"error": "Not found"})
        except (OSError, ValueError, KeyError, TypeError):
            status = 2
        finally:
            export_event(service, trace, span, parent, operation, start, status, values)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8084), Handler).serve_forever()
