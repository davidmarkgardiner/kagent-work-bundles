"""Project-scoped read-only GitLab MCP with bounded results and native trace context."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from workflow_demo import export_event

TOOLS = {
    "gitlab_get_project": "Read the configured GitLab project's current metadata.",
    "gitlab_list_issues": "Read up to five recent issues from the configured project. No descriptions or comments.",
    "gitlab_get_latest_pipeline": "Read the configured project's most recent pipeline status. Does not trigger a pipeline.",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def read_tool(name, trace, parent):
    base = os.environ["GITLAB_API_URL"].rstrip("/")
    url = urllib.parse.urlparse(base)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Require an approved HTTPS GitLab API URL")
    project = urllib.parse.quote(os.environ["GITLAB_PROJECT"], safe="")
    paths = {"gitlab_get_project": "", "gitlab_list_issues": "/issues?per_page=5&order_by=updated_at&sort=desc",
             "gitlab_get_latest_pipeline": "/pipelines?per_page=1&order_by=id&sort=desc"}
    span, start, status = uuid.uuid4().hex[:16], time.time_ns(), 0
    try:
        request = urllib.request.Request(base + "/projects/" + project + paths[name], headers={
            "Authorization": "Bearer " + os.environ["GITLAB_TOKEN"], "Accept": "application/json",
            "traceparent": f"00-{trace}-{span}-01"})
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=15) as response:
            status = response.status
            data = response.read(262145)
            if len(data) > 262144:
                raise ValueError("GitLab response exceeds the transport limit")
            raw = json.loads(data)
        if name == "gitlab_get_project":
            result = {k: raw.get(k) for k in ["id", "name", "default_branch", "archived", "visibility", "last_activity_at"]}
        elif name == "gitlab_list_issues":
            result = {"issues": [{k: (item.get(k)[:160] if k == "title" and isinstance(item.get(k), str) else item.get(k))
                                  for k in ["iid", "title", "state", "updated_at"]} for item in raw[:5]], "limit": 5}
        else:
            result = {"pipelines": [{k: item.get(k) for k in ["id", "status", "ref", "sha", "updated_at"]} for item in raw[:1]], "limit": 1}
        if len(json.dumps(result).encode()) > 8192:
            raise ValueError("GitLab result exceeds the result limit")
        return {"simulated": False, **result}
    except urllib.error.HTTPError as error:
        status = error.code
        with error:
            error.read(65536)
        raise ValueError("GitLab rejected the configured read") from None
    finally:
        export_event("flow-gitlab-mcp", trace, span, parent, "GET GitLab " + name, start,
                     1 if status == 200 else 2, {"flow.component": "mcp", "flow.tool.system": "GitLab API",
                     "flow.simulated": False, "http.request.method": "GET", "http.response.status_code": status})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply(200 if self.path == "/healthz" else 404, {"mode": "live-read-only"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.path != "/mcp" or not 0 < length <= 32768:
                return self.reply(400, {"error": "Invalid MCP request"})
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("params", {}), dict):
                raise ValueError("Invalid request")
        except (ValueError, OSError):
            return self.reply(400, {"error": "Invalid request"})
        carrier = re.fullmatch(r"00-([a-f0-9]{32})-([a-f0-9]{16})-[a-f0-9]{2}", self.headers.get("traceparent", ""))
        trace, parent = carrier.groups() if carrier else (uuid.uuid4().hex, "")
        span, start, status = uuid.uuid4().hex[:16], time.time_ns(), 1
        method, params = payload.get("method"), payload.get("params", {})
        values = {"flow.component": "mcp", "flow.tool.system": "GitLab MCP", "flow.simulated": False}
        try:
            if method == "initialize":
                result = {"protocolVersion": params.get("protocolVersion", "2025-03-26"), "capabilities": {"tools": {}},
                          "serverInfo": {"name": "flow-gitlab-read-only", "version": "1.0"}}
            elif method == "tools/list":
                result = {"tools": [{"name": name, "description": description, "annotations": {"readOnlyHint": True},
                           "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}
                          for name, description in TOOLS.items()]}
            elif method == "tools/call":
                name = params.get("name")
                if name not in TOOLS or params.get("arguments", {}) not in ({}, None):
                    raise ValueError("Only fixed read tools with no arguments are available")
                values["gen_ai.tool.name"] = name
                result = {"content": [{"type": "text", "text": json.dumps(read_tool(name, trace, span))}], "isError": False}
            elif str(method).startswith("notifications/"):
                return self.reply(202, {})
            elif method == "ping":
                result = {}
            else:
                raise ValueError("Unsupported MCP method")
        except (ValueError, OSError, KeyError, TypeError):
            status = 2
            result = {"content": [{"type": "text", "text": "Read failed. Check the configured project, short-lived credential, and private server logs."}], "isError": True}
        try:
            self.reply(200, {"jsonrpc": "2.0", "id": payload.get("id"), "result": result})
        finally:
            export_event("flow-gitlab-mcp", trace, span, parent, "MCP " + str(method), start, status, values)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8084), Handler).serve_forever()
