"""Bounded, metadata-only projection of OTLP traces into an activity graph."""
from collections import OrderedDict, deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.parse

COMPONENTS = [
    ("client", "Caller"), ("kagent", "kagent"),
    ("substrate", "Agent Substrate"), ("worker", "Worker pool"),
    ("actor", "Sandbox actor"), ("agentgateway", "agentgateway"),
    ("model", "Model provider"), ("mcp", "MCP tools"),
    ("skills", "Skills and knowledge"),
]
NATIVE_METADATA = {
    "kagent.runtime", "kagent.genai.producer", "gen_ai.agent.id", "gen_ai.agent.name",
    "gen_ai.main_agent.id", "gen_ai.main_agent.name", "gen_ai.conversation.id",
    "a2a.task.id", "a2a.method", "a2a.task.state", "kagent.invocation.segment", "kagent.invocation.disposition",
}
MODEL_OPERATIONS = {"generate_content", "chat", "text_completion", "embeddings"}
NATIVE_REQUEST_OPERATIONS = MODEL_OPERATIONS | {"execute_tool", "invoke_agent"}
ALLOWED = {
    "flow.execution.mode", "service.name", "service.namespace", "service.version", "kagent.agent.name", "kagent.name",
    "gen_ai.operation.name", "gen_ai.request.model", "gen_ai.response.model",
    "gen_ai.system", "gen_ai.provider.name", "gen_ai.tool.name", "gen_ai.tool.type", "gen_ai.tool.call.id", "gen_ai.task.id", "tool.name",
    "rpc.method", "mcp.method.name", "mcp.tool.name", "http.request.method",
    "http.method", "http.response.status_code", "http.status_code", "http.status", "http.path",
    "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens", "gen_ai.usage.cache_creation.input_tokens",
    "gen_ai.usage.cost", "gen_ai.usage.cost_usd", "gen_ai.cost.total",
    "llm.usage.prompt_tokens", "llm.usage.completion_tokens",
    "llm.token_count.prompt", "llm.token_count.completion",
    "gen_ai.usage.prompt_tokens", "gen_ai.usage.completion_tokens",
    "flow.component", "flow.destination", "flow.agent", "flow.result",
    "substrate.actor.id", "substrate.worker.id", "substrate.operation",
    "event.name", "gen_ai.event.name",
    "ate.actor.name", "ate.actor.uid", "ate.atespace", "ate.actor.state",
    "ate.template.name", "ate.template.atespace", "ate.worker.name", "ate.worker.uid",
    "ate.worker_pool.name", "kagent.session.id", "kagent.agent.namespace",
    "flow.simulated", "flow.workflow", "flow.tool.system", "flow.execution.id", "flow.evidence.source",
    "flow.security.subject", "flow.security.resource", "flow.security.decision", "flow.security.authority",
    "flow.security.expected_status", "flow.security.observed_status", "flow.security.backend_delta", "flow.security.check",
} | NATIVE_METADATA


def attrs(items):
    result = {}
    if not isinstance(items, list):
        raise ValueError("attributes must be an array")
    for item in items:
        key = item.get("key")
        if key in {"http.url", "url.full"}:
            try:
                target = urllib.parse.urlsplit(os.environ.get("MODEL_GATEWAY_URL", ""))
                raw_url = item.get("value", {}).get("stringValue", "")
                actual = urllib.parse.urlsplit(raw_url) if isinstance(raw_url, str) and len(raw_url) <= 2048 else None
                if (actual and target.scheme in {"http", "https"} and target.hostname
                        and (actual.scheme, actual.hostname, actual.port) == (target.scheme, target.hostname, target.port)
                        and not any((actual.username, actual.password, actual.query, actual.fragment,
                                     target.username, target.password, target.query, target.fragment))
                        and actual.path.startswith(target.path.rstrip('/') + '/')):
                    result['flow.destination'] = 'agentgateway'
            except (ValueError, TypeError):
                pass
            continue
        if key not in ALLOWED:
            continue
        value = item.get("value", {})
        for field in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if field in value:
                val = value[field]
                if key == "http.path":
                    val = str(val).split("?", 1)[0].split("#", 1)[0]
                    if not val.startswith("/"):
                        val = "[path omitted]"
                if isinstance(val, (str, int, float, bool)):
                    if isinstance(val, (int, float)) and (not math.isfinite(val) or abs(val) > 1e15):
                        raise ValueError("Invalid numeric attribute")
                    result[key] = val[:256] if isinstance(val, str) else val
                break
    return result


def number(values, keys):
    for key in keys:
        if key in values:
            try:
                val = float(values[key])
                return val if math.isfinite(val) and 0 <= val <= 1e15 else None
            except (ValueError, TypeError):
                return None
    return None


@dataclass(frozen=True)
class Span:
    traceId: str
    spanId: str
    parentSpanId: str
    name: str
    service: str
    component: str
    startNs: int
    endNs: int
    status: str
    attributes: dict
    receivedAt: float
    kind: str = "unspecified"
    otelStatus: str = "unset"
    toolExecution: str = ""
    toolCategory: str = ""


@dataclass(frozen=True)
class LogRecord:
    id: str
    timestampNs: str
    traceId: str
    spanId: str
    service: str
    severity: str
    severityNumber: int
    event: str
    message: str
    attributes: dict


def parse_logs(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("resourceLogs"), list):
        raise ValueError("Expected OTLP JSON resourceLogs array")
    records = []
    log_keys = {"service.name", "service.version", "event.name", "gen_ai.event.name",
                "gen_ai.request.model", "gen_ai.response.model", "gen_ai.operation.name",
                "gen_ai.tool.name", "mcp.tool.name", "http.method", "http.request.method",
                "http.status_code", "http.response.status_code", "http.status", "http.path", "gen_ai.usage.input_tokens",
                "gen_ai.usage.output_tokens", "gen_ai.provider.name", "gen_ai.system",
                "ate.actor.name", "ate.actor.uid", "ate.atespace", "ate.actor.state",
                "ate.template.name", "ate.template.atespace", "ate.worker.name", "ate.worker.uid",
                "ate.worker_pool.name", "kagent.session.id", "flow.simulated", "flow.workflow", "flow.result"} | NATIVE_METADATA
    for resource in payload["resourceLogs"]:
        resource_attrs = attrs(resource.get("resource", {}).get("attributes", []))
        service = str(resource_attrs.get("service.name", "unknown"))[:128]
        for scope in resource.get("scopeLogs", []):
            for raw in scope.get("logRecords", []):
                timestamp = int(raw.get("timeUnixNano", 0)) or int(raw.get("observedTimeUnixNano", 0))
                if not 0 <= timestamp < 2**64:
                    raise ValueError("Invalid log timestamp")
                trace_id, span_id = raw.get("traceId", ""), raw.get("spanId", "")
                for value, size in ((trace_id, 32), (span_id, 16)):
                    if not isinstance(value, str) or (value and not re.fullmatch(rf"[a-fA-F0-9]{{{size}}}", value)):
                        raise ValueError("Invalid log correlation ID")
                trace_id = trace_id.lower() if trace_id and int(trace_id, 16) else ""
                span_id = span_id.lower() if span_id and int(span_id, 16) else ""
                values = {k:v for k,v in {**resource_attrs, **attrs(raw.get("attributes", []))}.items() if k in log_keys}
                severity_number = int(raw.get("severityNumber", 0))
                if not 0 <= severity_number <= 24:
                    raise ValueError("Invalid severity number")
                severity = ("FATAL" if severity_number >= 21 else "ERROR" if severity_number >= 17 else
                            "WARN" if severity_number >= 13 else "INFO" if severity_number >= 9 else
                            "DEBUG" if severity_number >= 5 else "TRACE" if severity_number else "UNSPECIFIED")
                event = str(raw.get("eventName") or values.get("event.name") or values.get("gen_ai.event.name") or "OTel event")
                if not re.fullmatch(r"[a-zA-Z0-9_. -]{1,100}", event):
                    event = "OTel event"
                method = values.get("http.request.method") or values.get("http.method")
                status = values.get("http.response.status_code") or values.get("http.status_code") or values.get("http.status")
                model = values.get("gen_ai.response.model") or values.get("gen_ai.request.model")
                if component(service, "", {}) == "agentgateway":
                    request = " ".join(str(v) for v in (method or "HTTP request", values.get("http.path")) if v)
                    message = " · ".join(str(v) for v in (request, status, model) if v is not None)
                elif tool := values.get("gen_ai.tool.name") or values.get("mcp.tool.name"):
                    message = "Tool " + str(tool) + (" · " + str(status) if status is not None else "")
                elif method:
                    message = str(method) + " request" + (" · " + str(status) if status is not None else "")
                else:
                    message = event + " · message content omitted"
                body_digest = hashlib.sha256(json.dumps(raw.get("body"), sort_keys=True, allow_nan=False).encode()).hexdigest()
                identity = repr((timestamp, trace_id, span_id, service, severity_number, event, sorted(values.items()), body_digest))
                records.append(LogRecord(hashlib.sha256(identity.encode()).hexdigest()[:24], str(timestamp), trace_id, span_id,
                                         service, severity, severity_number, event, message, values))
                if len(records) > 4000:
                    raise ValueError("Export exceeds 4000 logs")
    return records


def native_runtime_identity(values):
    runtime = values.get("kagent.runtime")
    if runtime not in {"adk-go", "claude", "codex"}:
        try:
            identities = json.loads(os.environ.get('ORDINARY_AGENT_IDENTITIES', '[]'))
            if not isinstance(identities, list) or len(identities) > 8:
                return None
            for identity in identities:
                if (isinstance(identity, dict) and set(identity) in ({'namespace', 'name'}, {'namespace', 'name', 'serviceName', 'serviceNamespace'})
                        and all(isinstance(identity[k], str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}', identity[k])
                                for k in ('namespace', 'name'))
                        and all(isinstance(identity.get(k, ''), str) and re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,252}', identity[k])
                                for k in ('serviceName', 'serviceNamespace') if k in identity)
                        and values.get('service.name') == identity.get('serviceName', identity['name'])
                        and values.get('service.namespace') == identity.get('serviceNamespace', identity['namespace'])):
                    return {'runtime': 'adk-python', 'agentId': identity['namespace'] + '/' + identity['name'],
                            'agentName': identity['name'], 'source': 'sdk-resource-and-reviewed-profile'}
        except (ValueError, TypeError):
            pass
        return None
    return {"runtime": runtime,
            "agentId": values.get("gen_ai.main_agent.id") or values.get("gen_ai.agent.id"),
            "agentName": values.get("gen_ai.main_agent.name") or values.get("gen_ai.agent.name")}


def native_request(span):
    return bool(native_runtime_identity(span.attributes) and span.attributes.get("gen_ai.operation.name") in NATIVE_REQUEST_OPERATIONS)


def component(service, name, values):
    explicit = values.get("flow.component")
    if explicit in dict(COMPONENTS):
        return explicit
    if native_runtime_identity(values):
        return "kagent"
    service = service.lower().replace("_", "-")
    if "agentgateway" in service or service == "kimi-lab-gateway":
        return "agentgateway"
    if service in {"otel-substrate-reader", "otel-flow-reader", "flow-demo-agent"}:
        return "kagent"
    if service.startswith("ateom"):
        return "worker"
    if service in {"ateapi", "atecontroller", "atenet-router", "atenet-egress"}:
        return "actor" if "actor" in name.lower() and values.get("ate.actor.name") else "substrate"
    if "substrate" in service or service.startswith(("ate-", "atelet")):
        if "actor" in name.lower() or "substrate.actor.id" in values:
            return "actor"
        if "worker" in name.lower() or "substrate.worker.id" in values:
            return "worker"
        return "substrate"
    if "flow-client" in service:
        return "client"
    if "kagent" in service or "otel-flow-reader" in service:
        return "kagent"
    if "mcp" in service:
        return "mcp"
    return "unknown"


def tool_category(service, name, values):
    tool = values.get("gen_ai.tool.name") or values.get("mcp.tool.name") or values.get("tool.name")
    if not tool:
        return ""
    if (values.get("mcp.tool.name") or values.get("mcp.method.name")
            or values.get("flow.destination") == "mcp" or component(service, name, values) == "mcp"):
        return "mcp"
    identity = native_runtime_identity(values)
    if identity:
        if (identity["runtime"] == "adk-go" and values.get("gen_ai.operation.name") == "execute_tool"
                and tool in {"load_skill", "load_skill_resource"}):
            return "skill"
        if identity['runtime'] == 'adk-python' and values.get('gen_ai.operation.name') == 'execute_tool':
            if (tool, values.get('gen_ai.tool.type')) in {('skills', 'SkillsTool'), ('read_file', 'ReadFileTool')}:
                return 'skill'
            if values.get('gen_ai.tool.type') in {'McpTool', 'MCPTool'}:
                return 'mcp'
        return "native"
    return ""


def tool_execution(kind, service, name, values):
    tool = values.get("gen_ai.tool.name") or values.get("mcp.tool.name") or values.get("tool.name")
    if not tool:
        return ""
    category = tool_category(service, name, values)
    if category in {"skill", "native"}:
        if values.get("gen_ai.operation.name") == "execute_tool" and kind in (1, "SPAN_KIND_INTERNAL"):
            return "native-skill" if category == "skill" else "native-internal"
        return ""
    if kind in (2, "SPAN_KIND_SERVER"):
        return "server"
    # Pinned kagent tools 0.3.0 starts internal spans inside its tool handler.
    if (kind in (1, "SPAN_KIND_INTERNAL") and service == "flow-kubernetes-mcp"
            and tool in {"k8s_get_resources", "k8s_get_events"} and name == "mcp.tool." + tool):
        return "kagent-tools-internal"
    return ""


def parse_otlp(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("resourceSpans"), list):
        raise ValueError("Expected OTLP JSON resourceSpans array")
    parsed = []
    for resource in payload["resourceSpans"]:
        resource_attrs = attrs(resource.get("resource", {}).get("attributes", []))
        service = str(resource_attrs.get("service.name", "unknown"))[:128]
        for scope in resource.get("scopeSpans", []):
            for raw in scope.get("spans", []):
                trace, span, parent = raw.get("traceId", ""), raw.get("spanId", ""), raw.get("parentSpanId", "")
                if not isinstance(trace, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", trace) or int(trace, 16) == 0:
                    raise ValueError("Invalid trace ID")
                if not isinstance(span, str) or not re.fullmatch(r"[a-fA-F0-9]{16}", span) or int(span, 16) == 0:
                    raise ValueError("Invalid span ID")
                if parent and (not isinstance(parent, str) or not re.fullmatch(r"[a-fA-F0-9]{16}", parent)):
                    raise ValueError("Invalid parent span ID")
                start, end = int(raw.get("startTimeUnixNano", 0)), int(raw.get("endTimeUnixNano", 0))
                if start <= 0 or end < start:
                    raise ValueError("Invalid span timestamps")
                values = {**resource_attrs, **attrs(raw.get("attributes", []))}
                name = str(raw.get("name", "unnamed"))[:180]
                if re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s", name):
                    method = name.split()[0]
                    suffix = " /" if name in (f"{method} /", f"{method} / http receive", f"{method} / http send") else " request"
                    name = method + suffix
                else:
                    name = re.sub(r"https?://\S+", "[endpoint]", name)
                otel_status = {1: "ok", 2: "error", "STATUS_CODE_OK": "ok", "STATUS_CODE_ERROR": "error"}.get(raw.get("status", {}).get("code"), "unset")
                parsed.append(Span(trace.lower(), span.lower(), parent.lower(), name, service,
                                   component(service, name, values), start, end,
                                   "unknown" if native_runtime_identity(values) and otel_status == "unset" else "error" if otel_status == "error" else "ok",
                                   values, time.time(),
                                   {1: "internal", 2: "server", 3: "client", "SPAN_KIND_INTERNAL": "internal", "SPAN_KIND_SERVER": "server", "SPAN_KIND_CLIENT": "client"}.get(raw.get("kind"), "unspecified"),
                                   otel_status,
                                   tool_execution(raw.get("kind"), service, name, values),
                                   tool_category(service, name, values)))
                if len(parsed) > 4000:
                    raise ValueError("Export exceeds 4000 spans")
    return parsed


class ActivityStore:
    def __init__(self, max_traces=200, max_spans=4000, prices=None):
        self.lock = threading.Lock()
        self.traces = OrderedDict()
        self.max_traces, self.max_spans = max_traces, max_spans
        self.prices = prices or {}
        self.revision = 0
        self.last_received = None
        self.logs = OrderedDict()
        self.max_logs = 1000
        self.log_revision = 0
        self.focus_trace = None
        self.focus_actor = None
        self.recent_requests = deque(maxlen=8)
        self.recent_native_requests = deque(maxlen=8)

    def focus(self, trace_id, actor_name=None):
        with self.lock:
            self.focus_trace, self.focus_actor = trace_id, actor_name
            if trace_id and trace_id not in self.recent_requests:
                self.recent_requests.append(trace_id)

    def actor_activity(self, snapshot, actor_name, request_trace, actor_identity=None):
        if not actor_name:
            return None
        def matches(values):
            if actor_identity and actor_identity.get("ate.actor.uid"):
                return values.get("ate.actor.uid") == actor_identity["ate.actor.uid"]
            return (values.get("ate.actor.name") == actor_name and
                    (not actor_identity or not actor_identity.get("ate.atespace") or
                     values.get("ate.atespace") == actor_identity["ate.atespace"]))
        with self.lock:
            events = [r for r in self.logs.values() if matches(r.attributes)]
        trace_ids = {request_trace} | {r.traceId for r in events if r.traceId}
        for trace in snapshot["traces"]:
            if any(matches(s["attributes"]) for s in trace["spans"]):
                trace_ids.add(trace["traceId"])
        related = [t for t in snapshot["traces"] if t["traceId"] in trace_ids]
        states = [{"state": r.attributes["ate.actor.state"], "timestampNs": r.timestampNs,
                   "traceId": r.traceId} for r in sorted(events, key=lambda r: int(r.timestampNs))
                  if r.attributes.get("ate.actor.state")]
        return {"actorName": actor_name, "requestTraceId": request_trace, "traceIds": [t["traceId"] for t in related],
                "components": sorted({c for t in related for c in t["components"]}),
                "edges": [dict(e, traceId=t["traceId"]) for t in related for e in t["edges"]],
                "states": states[-12:]}

    def observed_activity(self, snapshot, request_trace):
        request = next((t for t in snapshot["traces"] if t["traceId"] == request_trace and t["nativeRequest"]), None)
        if not request:
            return None
        identity = {}
        for key in ("ate.actor.name", "ate.actor.uid", "ate.atespace"):
            values = {s["attributes"][key] for s in request["spans"] if s["attributes"].get(key)}
            if len(values) > 1:
                return None
            if values:
                identity[key] = values.pop()
        return self.actor_activity(snapshot, identity.get("ate.actor.name"), request_trace, identity)

    def ingest_logs(self, payload):
        records = parse_logs(payload)
        with self.lock:
            for record in records:
                if record.id not in self.logs:
                    self.logs[record.id] = record
                    self.log_revision += 1
            while len(self.logs) > self.max_logs:
                self.logs.popitem(last=False)
        return len(records)

    def logs_snapshot(self, trace_id=None, service=None):
        with self.lock:
            records = sorted((r for r in self.logs.values() if (not trace_id or r.traceId == trace_id) and (not service or r.service == service)),
                             key=lambda r: int(r.timestampNs), reverse=True)
            return {"revision": self.log_revision, "retained": len(self.logs), "matching": len(records),
                    "limit": 200, "maxLogs": self.max_logs, "services": sorted({r.service for r in self.logs.values()}), "logs": [asdict(r) for r in records[:200]]}

    def ingest(self, payload):
        spans = parse_otlp(payload)
        with self.lock:
            for span in spans:
                bucket = self.traces.setdefault(span.traceId, OrderedDict())
                if span.spanId in bucket:
                    continue
                bucket[span.spanId] = span
                self.traces.move_to_end(span.traceId)
                self.revision += 1
                self.last_received = span.receivedAt
                if native_request(span):
                    if span.traceId in self.recent_native_requests:
                        self.recent_native_requests.remove(span.traceId)
                    self.recent_native_requests.append(span.traceId)
            manual = set(self.recent_requests) | {self.focus_trace} | {record.traceId for record in self.logs.values()
                         if self.focus_actor and record.attributes.get("ate.actor.name") == self.focus_actor
                         and record.attributes.get("ate.actor.state") and record.traceId}
            protected = manual | set(self.recent_native_requests)
            while len(self.traces) > self.max_traces or sum(map(len, self.traces.values())) > self.max_spans:
                background = {
                    ("ateapi", "ateapi.Control/ListActors"),
                    ("atenet-router", "ateapi.Control/ListActors"), ("atenet-router", "HTTP GET"),
                    ("atelet", "ateom.Ateom/GetActiveWorkloadStats"),
                    ("ateom-gvisor", "ateom.Ateom/GetActiveWorkloadStats"),
                }
                victim = next((key for key, bucket in self.traces.items()
                               if key not in protected and all((s.service, s.name) in background and not s.attributes.get("ate.actor.name")
                                      for s in bucket.values())),
                              next((key for key in self.traces if key not in protected),
                                   next((key for key in self.recent_native_requests if key in self.traces and key not in manual),
                                        next(iter(self.traces)))))
                del self.traces[victim]
        return len(spans)

    def snapshot(self):
        with self.lock:
            traces = [self.project(k, list(v.values())) for k, v in reversed(self.traces.items())]
            observed = {c for t in traces for c in t["components"]}
            return {"revision": self.revision, "lastReceivedAt": self.last_received,
                    "retention": {"maxTraces": self.max_traces, "maxSpans": self.max_spans},
                    "components": [{"id": c, "label": label, "availability": "observed" if c in observed else "unobserved"}
                                   for c, label in COMPONENTS], "traces": traces}

    def project(self, trace_id, spans):
        by_id = {s.spanId: s for s in spans}
        edges, nodes = {}, set()
        llm = []
        def edge(origin, target, basis, span_id):
            entry = edges.setdefault((origin, target), {"from": origin, "to": target, "basis": basis, "spanIds": []})
            if span_id not in entry["spanIds"]:
                entry["spanIds"].append(span_id)
        for span in spans:
            a = span.attributes
            if span.component != "unknown":
                nodes.add(span.component)
            parent = by_id.get(span.parentSpanId)
            if parent and parent.component != span.component and "unknown" not in (parent.component, span.component):
                edge(parent.component, span.component, "parent span", span.spanId)
            model = a.get("gen_ai.response.model") or a.get("gen_ai.request.model") or None
            in_tokens = number(a, ("gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens", "llm.usage.prompt_tokens", "llm.token_count.prompt"))
            out_tokens = number(a, ("gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens", "llm.usage.completion_tokens", "llm.token_count.completion"))
            native_identity = native_runtime_identity(a)
            legacy_openai = (native_identity and native_identity['runtime'] == 'adk-python'
                             and span.name == 'openai.chat' and span.kind == 'client' and a.get('gen_ai.system') == 'openai')
            if (span.component in ("kagent", "agentgateway") and
                    ((native_identity and (a.get("gen_ai.operation.name") in MODEL_OPERATIONS or legacy_openai)) or (model and not native_identity))):
                nodes.add("model")
                edge(span.component, "model", "model span", span.spanId)
                llm.append((span, model, in_tokens, out_tokens))
            tool = a.get("gen_ai.tool.name") or a.get("mcp.tool.name") or a.get("tool.name")
            if tool and span.component in ("kagent", "agentgateway") and span.toolCategory in {"skill", "mcp"}:
                target = "skills" if span.toolCategory == "skill" else "mcp"
                nodes.add(target)
                edge(span.component, target, "native skill span" if target == "skills" else "tool span", span.spanId)
            dest = a.get("flow.destination")
            if dest in dict(COMPONENTS) and dest != span.component and span.component != "unknown":
                nodes.add(dest)
                edge(span.component, dest, "instrumented destination", span.spanId)
        def descendant(child, ancestor):
            seen = set()
            while child.parentSpanId in by_id and child.parentSpanId not in seen:
                seen.add(child.parentSpanId)
                child = by_id[child.parentSpanId]
                if child.spanId == ancestor.spanId:
                    return True
            return False
        def same_model(left, right):
            keys = ("gen_ai.request.model", "gen_ai.response.model")
            return bool({left.attributes[k] for k in keys if left.attributes.get(k)} &
                        {right.attributes[k] for k in keys if right.attributes.get(k)})
        native_reports = [report for report in llm if native_runtime_identity(report[0].attributes)]
        model_usage_source = "native-runtime" if native_reports else "reconciled-reports" if llm else None
        model_reports = native_reports or llm
        excluded_reports = sum(report[0].component != "agentgateway" and not native_runtime_identity(report[0].attributes)
                               for report in llm) if native_reports else 0
        calls = []
        for span, model, inp, out in model_reports:
            if any(descendant(other, span) and same_model(other, span) for other, _, _, _ in model_reports):
                continue
            calls.append((span, model, inp, out))
        reconciled = []
        cost_keys = ("gen_ai.usage.cost_usd", "gen_ai.usage.cost", "gen_ai.cost.total")
        for span, model, inp, out in calls:
            cost = number(span.attributes, cost_keys)
            ancestor = by_id.get(span.parentSpanId)
            visited = set()
            while ancestor and ancestor.spanId not in visited:
                visited.add(ancestor.spanId)
                reports = [r for r in model_reports if r[0].spanId == ancestor.spanId and same_model(span, ancestor)]
                if reports and sum(descendant(leaf, ancestor) and same_model(leaf, ancestor) for leaf, _, _, _ in calls) == 1:
                    _, _, ancestor_input, ancestor_output = reports[0]
                    inp = ancestor_input if inp is None else inp
                    out = ancestor_output if out is None else out
                    cost = number(ancestor.attributes, cost_keys) if cost is None else cost
                ancestor = by_id.get(ancestor.parentSpanId)
            reconciled.append((span, model, inp, out, cost))
        costs, inputs, outputs = [], [], []
        calls_data = []
        for span, model, inp, out, cost in reconciled:
            source = "reported" if cost is not None else "unknown"
            price = self.prices.get(model) if model_usage_source != "native-runtime" else None
            if cost is None and price and inp is not None and out is not None:
                cost = (inp * price["inputPerMillion"] + out * price["outputPerMillion"]) / 1000000
                source = "estimated"
            if cost is not None:
                costs.append(cost)
            if inp is not None:
                inputs.append(inp)
            if out is not None:
                outputs.append(out)
            calls_data.append({"spanId": span.spanId, "model": model, "inputTokens": inp, "outputTokens": out,
                               "costUsd": cost, "costSource": source, "pricingSource": price.get("source") if price else None})
        if not native_reports and ("kagent", "agentgateway") in edges and not any(s.component == "kagent" for s, _, _, _ in calls):
            edges.pop(("kagent", "model"), None)
        start, end = min(s.startNs for s in spans), max(s.endNs for s in spans)
        root_call = next((s for s in spans if s.component == "client" and not s.parentSpanId), None)
        native_identity = next((identity for s in spans if (identity := native_runtime_identity(s.attributes))), None)
        return {"traceId": trace_id, "executionMode": 'ordinary' if native_identity and native_identity['runtime'] == 'adk-python' else next((s.attributes["flow.execution.mode"] for s in spans if s.attributes.get("flow.execution.mode") in {"standalone", "substrate", "a2a"}), None), "startNs": str(start), "durationMs": (end-start)/1e6,
                "nativeRuntimeIdentity": native_identity,
                "nativeRequest": any(native_request(s) for s in spans),
                "receivedAt": max(s.receivedAt for s in spans), "spanCount": len(spans),
                "status": root_call.status if root_call else ("error" if any(s.status == "error" for s in spans) else "unknown" if native_identity or all(s.status == "unknown" for s in spans) else "ok"),
                "errorSpanCount": sum(s.status == "error" for s in spans),
                "modelUsageSource": model_usage_source,
                "excludedModelReports": excluded_reports,
                "inputTokens": sum(inputs) if inputs else None, "outputTokens": sum(outputs) if outputs else None,
                "usageComplete": bool(calls) and not excluded_reports and len(inputs) == len(calls) and len(outputs) == len(calls),
                "costUsd": sum(costs) if costs else None,
                "costSource": "unknown" if not costs else ("partial" if excluded_reports or len(costs) != len(calls) else ("estimated" if any(c["costSource"] == "estimated" for c in calls_data) else "reported")),
                "components": sorted(nodes), "edges": list(edges.values()), "modelCalls": calls_data,
                "spans": [{**asdict(s), "startNs": str(s.startNs), "endNs": str(s.endNs), "durationMs": (s.endNs-s.startNs)/1e6} for s in sorted(spans, key=lambda s:s.startNs)]}
