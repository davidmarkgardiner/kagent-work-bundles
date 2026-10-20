"""Local POC HTTP server with a prompt caller for one read-only A2A agent."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from telemetry import ActivityStore

ROOT = Path(os.path.abspath(__file__)).parent
price_path = os.getenv("PRICING_FILE")
STORE = ActivityStore(prices=json.loads(Path(price_path).read_text()) if price_path else {})
INVOKING = threading.Lock()
INVOCATION = {"status": "idle"}
MAX_PROMPT_CHARS = 4000


def invocation_prompt(payload):
    if not isinstance(payload, dict) or set(payload) != {"prompt"} or not isinstance(payload["prompt"], str):
        raise ValueError("Send a JSON object containing your prompt")
    prompt = payload["prompt"].strip()
    if not prompt:
        raise ValueError("Enter a prompt to send to the agent")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("The prompt must contain at most 4,000 characters")
    return prompt


def terminal_text(response):
    if "error" in response:
        raise ValueError("Agent returned a JSON-RPC error")
    result = response.get("result", {})
    if result.get("kind") == "task" or "status" in result:
        if result.get("status", {}).get("state") != "completed":
            raise ValueError("Agent task did not reach completed")
    elif result.get("kind") != "message":
        raise ValueError("Expected an A2A task or message")
    parts = [p for a in result.get("artifacts", []) for p in a.get("parts", [])]
    parts += result.get("parts", [])
    text = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")[:3000]
    if not text:
        raise ValueError("Agent returned no terminal text")
    return text


def post(url, payload, headers=None, timeout=90):
    req = urllib.request.Request(url, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read(1024 * 1024))


def invoke(prompt, trace):
    span = uuid.uuid4().hex[:16]
    start = time.time_ns()
    INVOCATION.clear()
    INVOCATION.update(status="running", traceId=trace, startedAt=time.time())
    STORE.focus(trace)
    status, text = 1, ""
    try:
        base = os.getenv("KAGENT_URL", "http://kagent-controller.kagent.svc.cluster.local:8083")
        name = os.getenv("AGENT_NAME", "otel-flow-reader")
        ns = os.getenv("AGENT_NAMESPACE", "kagent")
        url = os.getenv("AGENT_A2A_URL", f"{base}/api/a2a/{ns}/{name}/")
        headers = {"traceparent": f"00-{trace}-{span}-01"}
        if user_id := os.getenv("KAGENT_USER_ID"):
            headers["X-User-Id"] = user_id
        if os.getenv("AGENT_PROTOCOL") == "grpc":
            from substrate_call import invoke_session
            text = invoke_session(prompt, headers["traceparent"], INVOCATION,
                                  on_session=lambda actor_name: STORE.focus(trace, actor_name))
        else:
            response = post(url, {
            "jsonrpc": "2.0", "id": trace, "method": "message/send", "params": {"message": {
                "kind": "message", "messageId": uuid.uuid4().hex, "contextId": "flow-" + trace,
                "role": "user", "parts": [{"kind": "text", "text": prompt}]}}},
                headers)
            text = terminal_text(response)
        INVOCATION.update(status="completed", text=text)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, urllib.error.URLError):
        status = 2
        INVOCATION.update(status="failed", text="The agent call failed. Inspect the trace and the agent/model route.")
    finally:
        payload = {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "flow-client"}}]},
            "scopeSpans": [{"scope": {"name": "otel-agent-flow"}, "spans": [{"traceId": trace, "spanId": span,
                "name": "Agent prompt call", "kind": 3, "startTimeUnixNano": str(start),
                "endTimeUnixNano": str(time.time_ns()), "status": {"code": status},
                "attributes": [{"key": "flow.destination", "value": {"stringValue": "kagent"}}]}]}]}]}
        try:
            post(os.getenv("OTEL_ENDPOINT", "http://flow-collector:4318/v1/traces"), payload, timeout=10)
            INVOCATION["exportStatus"] = "exported"
        except (OSError, ValueError):
            INVOCATION["exportStatus"] = "failed"
        INVOCATION["finishedAt"] = time.time()
        INVOKING.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, data, content_type="application/json"):
        body = json.dumps(data, allow_nan=False).encode() if content_type == "application/json" else data
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/healthz":
            return self.send(200, {"ok": True})
        if path == "/api/state":
            snapshot = STORE.snapshot()
            invocation = dict(INVOCATION)
            activity = STORE.actor_activity(snapshot, invocation.get("actorName"), invocation.get("traceId"))
            return self.send(200, {**snapshot, "invocation": invocation, "sessionActivity": activity, "runtime": {
                "substrateInstalled": os.getenv("SUBSTRATE_INSTALLED") == "true",
                "demoMode": os.getenv("DEMO_MODE", ""),
                "demoPrompt": os.getenv("DEMO_PROMPT", ""),
                "label": os.getenv("RUNTIME_LABEL", "kagent 0.10.1 · agentgateway 1.5.0 · local kind POC"),
                "promptHelp": os.getenv("PROMPT_HELP", "Read-only inventory agent · Ctrl/⌘ + Enter to send. Each prompt starts a new run.")}})
        if path == "/api/logs":
            trace_id = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("traceId", [""])[0]
            if trace_id and not re.fullmatch(r"[a-fA-F0-9]{32}", trace_id):
                return self.send(400, {"error": "Invalid trace ID"})
            service = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("service", [""])[0]
            if len(service) > 128:
                return self.send(400, {"error": "Invalid service filter"})
            return self.send(200, STORE.logs_snapshot(trace_id.lower() or None, service or None))
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8"),
                 "/logs.css": ("logs.css", "text/css; charset=utf-8"),
                 "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if path in files:
            name, mime = files[path]
            return self.send(200, (ROOT / "ui" / name).read_bytes(), mime)
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host"):
            return self.send(403, {"error": "Cross-origin requests are disabled"})
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/invoke":
            if self.headers.get_content_type() != "application/json":
                return self.send(415, {"error": "Send your prompt as JSON"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32768:
                    return self.send(413, {"error": "Prompt request must be between 1 byte and 32 KiB"})
                self.connection.settimeout(10)
                prompt = invocation_prompt(json.loads(self.rfile.read(length)))
            except (ValueError, TypeError):
                return self.send(400, {"error": "Enter a non-empty prompt of at most 4,000 characters"})
            if not INVOKING.acquire(blocking=False):
                return self.send(409, {"error": "An invocation is already running"})
            trace = uuid.uuid4().hex
            INVOCATION.clear()
            INVOCATION.update(status="starting", traceId=trace)
            threading.Thread(target=invoke, args=(prompt, trace), daemon=True).start()
            return self.send(202, {"status": "started", "traceId": trace})
        if path not in ("/v1/traces", "/v1/logs"):
            return self.send(404, {"error": "Not found"})
        if self.headers.get_content_type() != "application/json":
            return self.send(415, {"error": "OTLP JSON required. Configure exporter encoding: json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2 * 1024 * 1024:
                return self.send(413, {"error": "Body must be between 1 byte and 2 MiB"})
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            if path == "/v1/logs":
                STORE.ingest_logs(payload)
            else:
                STORE.ingest(payload)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            return self.send(400, {"error": "Invalid OTLP JSON export"})
        self.send(200, {})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8787"))
    print(f"Agent flow listening on :{port}", flush=True)
    ThreadingHTTPServer((os.getenv("BIND_ADDRESS", "127.0.0.1"), port), Handler).serve_forever()
