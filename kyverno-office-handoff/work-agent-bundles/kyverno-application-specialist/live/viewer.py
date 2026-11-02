"""Read-only composition of received OTel activity and local recovery receipts."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from recovery import (HASH, NAME, InvalidMetadata, integer, obj, profile as validate_recovery_profile,
                      read_json, read_view, task_ids, text, unique_object, reject_constant)

MAX_RESPONSE = 4 * 1024 * 1024
MAX_ARCHIVE = 1024 * 1024
ARCHIVE_ATTRIBUTES = set("""flow.execution.mode service.name service.namespace service.version kagent.agent.name kagent.name
gen_ai.operation.name gen_ai.request.model gen_ai.response.model gen_ai.system gen_ai.provider.name
gen_ai.tool.name gen_ai.tool.type gen_ai.tool.call.id gen_ai.task.id tool.name rpc.method mcp.method.name
mcp.tool.name http.request.method http.method http.response.status_code http.status_code http.status http.path
gen_ai.usage.input_tokens gen_ai.usage.output_tokens gen_ai.usage.cache_read.input_tokens
gen_ai.usage.cache_creation.input_tokens gen_ai.usage.cost gen_ai.usage.cost_usd gen_ai.cost.total
llm.usage.prompt_tokens llm.usage.completion_tokens llm.token_count.prompt llm.token_count.completion
gen_ai.usage.prompt_tokens gen_ai.usage.completion_tokens flow.component flow.destination flow.agent flow.result
substrate.actor.id substrate.worker.id substrate.operation event.name gen_ai.event.name ate.actor.name
ate.actor.uid ate.atespace ate.actor.state ate.template.name ate.template.atespace ate.worker.name ate.worker.uid
ate.worker_pool.name kagent.session.id kagent.agent.namespace flow.simulated flow.workflow flow.tool.system
flow.execution.id flow.evidence.source flow.security.subject flow.security.resource flow.security.decision
flow.security.authority flow.security.expected_status flow.security.observed_status flow.security.backend_delta
flow.security.check kagent.runtime kagent.genai.producer gen_ai.agent.id gen_ai.agent.name gen_ai.main_agent.id
gen_ai.main_agent.name gen_ai.conversation.id a2a.task.id a2a.method a2a.task.state kagent.invocation.segment
kagent.invocation.disposition flow.incident.id flow.run.id flow.demo.step flow.demo.state
""".split())
TRACE_FIELDS = ("traceId", "executionMode", "startNs", "durationMs", "nativeRuntimeIdentity", "nativeRequest", "receivedAt",
                "spanCount", "status", "errorSpanCount", "modelUsageSource", "excludedModelReports", "inputTokens", "outputTokens",
                "usageComplete", "costUsd", "costSource", "components", "edges", "modelCalls", "spans")
SPAN_FIELDS = ("traceId", "spanId", "parentSpanId", "name", "service", "component", "startNs", "endNs", "status", "attributes",
               "receivedAt", "kind", "otelStatus", "toolExecution", "toolCategory", "durationMs")
LOG_FIELDS = ("id", "timestampNs", "traceId", "spanId", "service", "severity", "severityNumber", "event", "message", "attributes")
ADMISSION_SCOPE = ("schema_version", "run_id", "incident_id", "cluster_id", "namespace", "application",
                   "policy_name", "rule_name", "profile_revision")
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/logs.css": ("logs.css", "text/css; charset=utf-8"),
          "/favicon.svg": ("favicon.svg", "image/svg+xml")}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def archive_id(value, size):
    text(value, rf"[0-9a-f]{{{size}}}")
    if not int(value, 16):
        raise InvalidMetadata("Zero archive correlation ID")


def archive_number(value, nullable=False):
    if nullable and value is None:
        return
    if type(value) not in {int, float} or not 0 <= value <= 1e15 or not math.isfinite(value):
        raise InvalidMetadata("Invalid archive number")


def archive_timestamp(value):
    text(value, r"[0-9]{1,20}")
    if not 0 < int(value) < 2**64:
        raise InvalidMetadata("Invalid archived timestamp")


def archive_attributes(value, binding):
    if not isinstance(value, dict) or set(value) - ARCHIVE_ATTRIBUTES:
        raise InvalidMetadata("Unexpected archived attributes")
    for item in value.values():
        if isinstance(item, str):
            text(item, r"[^\x00-\x1f\x7f]{0,256}")
        elif type(item) is not bool:
            if type(item) not in {int, float} or not -1e15 <= item <= 1e15 or not math.isfinite(item):
                raise InvalidMetadata("Invalid archived attribute")
    if (task_ids({"attributes": value}) - {binding["taskId"]} or value.get("flow.simulated") is True
            or value.get("flow.incident.id", binding["incidentId"]) != binding["incidentId"]
            or value.get("flow.run.id", binding["runId"]) != binding["runId"]):
        raise InvalidMetadata("Archived task or incident does not match")


def validate_archived_trace(trace, plan, captured):
    obj(trace, TRACE_FIELDS)
    archive_id(trace["traceId"], 32)
    identity, binding = trace["nativeRuntimeIdentity"], plan["binding"]
    obj(identity, ("runtime", "agentId", "agentName"), ("source",))
    if (identity["agentId"] != plan["agent"]["namespace"] + "/" + plan["agent"]["name"]
            or identity["runtime"] not in {"adk-go", "adk-python", "claude", "codex"} or trace["nativeRequest"] is not True):
        raise InvalidMetadata("Unreviewed archive agent")
    if identity["agentName"] is not None:
        text(identity["agentName"])
    if "source" in identity:
        text(identity["source"])
    spans = trace["spans"]
    if not isinstance(spans, list) or not 1 <= len(spans) <= 512 or type(trace["spanCount"]) is not int or trace["spanCount"] != len(spans):
        raise InvalidMetadata("Invalid archived span count")
    archive_timestamp(trace["startNs"])
    for key in ("durationMs", "receivedAt"):
        archive_number(trace[key])
    if trace["receivedAt"] > captured + 1 or type(trace["usageComplete"]) is not bool:
        raise InvalidMetadata("Archive receipt time or usage is invalid")
    for key in ("inputTokens", "outputTokens", "costUsd"):
        archive_number(trace[key], nullable=True)
    for key in ("errorSpanCount", "excludedModelReports"):
        integer(trace[key], 0, 512)
    for key in ("status", "costSource"):
        text(trace[key])
    for key in ("executionMode", "modelUsageSource"):
        if trace[key] is not None:
            text(trace[key])
    ids, anchored = set(), False
    for span in spans:
        obj(span, SPAN_FIELDS)
        archive_id(span["spanId"], 16)
        if span["traceId"] != trace["traceId"] or span["spanId"] in ids:
            raise InvalidMetadata("Archived span identity mismatch")
        if span["parentSpanId"]:
            archive_id(span["parentSpanId"], 16)
        ids.add(span["spanId"])
        for key in ("startNs", "endNs"):
            archive_timestamp(span[key])
        if int(span["endNs"]) < int(span["startNs"]):
            raise InvalidMetadata("Archived span time order mismatch")
        for key in ("receivedAt", "durationMs"):
            archive_number(span[key])
        if span["receivedAt"] > captured + 1:
            raise InvalidMetadata("Archived span was not received at capture")
        for key in ("name", "service", "component", "status", "kind", "otelStatus", "toolExecution", "toolCategory"):
            text(span[key], r"[^\x00-\x1f\x7f]{0,180}")
        archive_attributes(span["attributes"], binding)
        anchored |= span["component"] == "kagent" and task_ids(span) == {binding["taskId"]}
    if not anchored:
        raise InvalidMetadata("No exact native task anchor in archive")
    if not isinstance(trace["components"], list) or len(trace["components"]) > 16:
        raise InvalidMetadata("Invalid archived components")
    for component in trace["components"]:
        text(component)
    if not isinstance(trace["edges"], list) or len(trace["edges"]) > 512 or not isinstance(trace["modelCalls"], list) or len(trace["modelCalls"]) > 512:
        raise InvalidMetadata("Invalid archived derived metadata")
    for edge in trace["edges"]:
        obj(edge, ("from", "to", "basis", "spanIds"))
        for key in ("from", "to"):
            text(edge[key])
        text(edge["basis"], r"[A-Za-z0-9 -]{1,100}")
        if not isinstance(edge["spanIds"], list) or len(edge["spanIds"]) > 512 or set(edge["spanIds"]) - ids:
            raise InvalidMetadata("Unretained archived edge span")
    for call in trace["modelCalls"]:
        obj(call, ("spanId", "model", "inputTokens", "outputTokens", "costUsd", "costSource", "pricingSource"))
        if call["spanId"] not in ids:
            raise InvalidMetadata("Unretained archived model span")
        text(call["costSource"])
        if call["model"] is not None:
            text(call["model"])
        if call["pricingSource"] is not None:
            text(call["pricingSource"], r"[^\x00-\x1f\x7f]{1,256}")
        for key in ("inputTokens", "outputTokens", "costUsd"):
            archive_number(call[key], nullable=True)
    return ids


def validate_archived_log(log, trace_spans, binding, captured=None):
    obj(log, LOG_FIELDS, ("receivedAt",))
    if "receivedAt" in log:
        archive_number(log["receivedAt"])
        if captured is not None and log["receivedAt"] > captured + 1:
            raise InvalidMetadata("Archived log receipt is after capture")
    text(log["id"], r"[0-9a-f]{24}")
    archive_timestamp(log["timestampNs"])
    if log["traceId"] not in trace_spans or log["spanId"] not in trace_spans[log["traceId"]]:
        raise InvalidMetadata("Archived log has no accepted trace/span")
    text(log["service"], r"[^\x00-\x1f\x7f]{1,128}")
    text(log["event"], r"[a-zA-Z0-9_. -]{1,100}")
    integer(log["severityNumber"], 0, 24)
    if log["severity"] not in {"FATAL", "ERROR", "WARN", "INFO", "DEBUG", "TRACE", "UNSPECIFIED"}:
        raise InvalidMetadata("Invalid archived severity")
    archive_attributes(log["attributes"], binding)
    attrs = log["attributes"]
    status = attrs.get("http.response.status_code") or attrs.get("http.status_code") or attrs.get("http.status")
    method = attrs.get("http.request.method") or attrs.get("http.method")
    tool = attrs.get("gen_ai.tool.name") or attrs.get("mcp.tool.name")
    messages = {log["event"] + " · message content omitted"}
    if tool:
        messages.add("Tool " + str(tool) + (" · " + str(status) if status is not None else ""))
    if method:
        messages.add(str(method) + " request" + (" · " + str(status) if status is not None else ""))
    if "agentgateway" in log["service"].lower().replace("_", "-") or log["service"] == "kimi-lab-gateway":
        request = " ".join(str(v) for v in (method or "HTTP request", attrs.get("http.path")) if v)
        messages.add(" · ".join(str(v) for v in (request, status, attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model")) if v is not None))
    if log["message"] not in messages:
        raise InvalidMetadata("Archive contains unsanitized log content")


def observed_archive(archive_path="/data/observed-traces.json", profile_path="/profile/profile.json", now=None):
    """Read historical received metadata without ingestion, restamping or authority inference."""
    try:
        with Path(archive_path).open("rb") as stream:
            raw = stream.read(MAX_ARCHIVE + 1)
        if len(raw) > MAX_ARCHIVE:
            raise InvalidMetadata("Archive exceeds limit")
        archive = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        plan = validate_recovery_profile(read_json(profile_path))
        obj(archive, ("schemaVersion", "source", "capturedAt", "traces"), ("logs",))
        if type(archive["schemaVersion"]) is not int or archive["schemaVersion"] != 1 or archive["source"] != "received-otel-dashboard" or plan["mode"] != "live":
            raise InvalidMetadata("Untrusted archive source")
        integer(archive["capturedAt"])
        if archive["capturedAt"] > (time.time() if now is None else now):
            raise InvalidMetadata("Future archive capture")
        if not isinstance(archive["traces"], list) or not 1 <= len(archive["traces"]) <= 4:
            raise InvalidMetadata("Archive trace limit exceeded")
        trace_spans = {}
        for trace in archive["traces"]:
            ids = validate_archived_trace(trace, plan, archive["capturedAt"])
            if trace["traceId"] in trace_spans:
                raise InvalidMetadata("Duplicate archived trace")
            trace_spans[trace["traceId"]] = ids
        logs = archive.get("logs", [])
        if not isinstance(logs, list) or len(logs) > 256:
            raise InvalidMetadata("Archive log limit exceeded")
        log_ids = set()
        for log in logs:
            validate_archived_log(log, trace_spans, plan["binding"], archive["capturedAt"])
            if log["id"] in log_ids:
                raise InvalidMetadata("Duplicate archived log")
            log_ids.add(log["id"])
        return archive
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return None


def merge_observed_traces(activity, archive):
    if not archive:
        return activity
    current = {trace["traceId"] for trace in activity.get("traces", [])}
    retained = [{**deepcopy(trace), "retainedSource": "operator-received-archive"}
                for trace in archive["traces"] if trace["traceId"] not in current]
    merged = {**activity, "traces": [*activity.get("traces", []), *retained]}
    return merged if len(json.dumps(merged, allow_nan=False).encode()) <= MAX_RESPONSE else activity


def merge_observed_logs(current, archive, trace_id="", service=""):
    if not archive or not archive.get("logs"):
        return current
    records = {log["id"]: {**deepcopy(log), "retainedSource": "operator-received-archive"} for log in archive.get("logs", [])}
    records.update({log["id"]: log for log in current.get("logs", [])})
    selected = sorted((log for log in records.values() if (not trace_id or log["traceId"] == trace_id)
                       and (not service or log["service"] == service)), key=lambda log: int(log["timestampNs"]), reverse=True)
    merged = {**current, "logs": selected, "retained": len(records), "matching": len(selected), "limit": len(selected),
              "countScope": "current-response-and-operator-archive",
              "upstreamRetained": current.get("retained"), "upstreamMatching": current.get("matching"),
              "services": sorted(set(current.get("services", [])) | {log["service"] for log in records.values()})}
    return merged if len(json.dumps(merged, allow_nan=False).encode()) <= MAX_RESPONSE else current


def pre_admission_view(status_path="/data/admission-status.json", profile_path="/profile/admission.json", now=None):
    """Bounded operator metadata only; never establishes a native task or recovery."""
    now = time.time() if now is None else now
    try:
        scope, status = read_json(profile_path), read_json(status_path)
        obj(scope, ADMISSION_SCOPE)
        obj(status, (*ADMISSION_SCOPE, "captured_at", "valid_denials", "classifier_attempts", "phase", "confidence", "threshold"))
        if type(scope["schema_version"]) is not int or scope["schema_version"] != 1:
            raise InvalidMetadata("Invalid admission scope version")
        for key in ADMISSION_SCOPE[1:]:
            text(scope[key], HASH if key == "profile_revision" else NAME if key in {"namespace", "application", "policy_name", "rule_name"} else r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
        if type(status["schema_version"]) is not int or any(status[key] != scope[key] for key in ADMISSION_SCOPE):
            raise InvalidMetadata("Admission status scope mismatch")
        integer(status["captured_at"])
        integer(status["valid_denials"], 0)
        integer(status["classifier_attempts"], 0, 12)
        confidence, threshold = status["confidence"], status["threshold"]
        if (not status["captured_at"] <= now <= status["captured_at"] + 300
                or status["phase"] not in {"observing", "suppressed", "unknown", "accepted"}
                or type(threshold) not in {float, int} or threshold != 0.95
                or (confidence is not None and (type(confidence) not in {float, int} or not 0 <= confidence <= 1 or not math.isfinite(confidence)))):
            raise InvalidMetadata("Admission status is unavailable or invalid")
    except (OSError, ValueError, TypeError, RecursionError):
        return None
    denials, attempts, phase = status["valid_denials"], status["classifier_attempts"], status["phase"]
    score = "not reported" if confidence is None else json.dumps(confidence)
    fault = f"{denials} known-good admission denials observed in the reviewed scope."
    classifier = f"Classifier phase {phase}; {attempts} attempts; confidence {score}; admission threshold 0.95."
    return {"enabled": True, "state": "unknown", "label": "Pre-admission · " + phase, "mode": "pre-admission",
            "preAdmissionScope": scope, "observerId": "operator-status-file",
            "capturedAt": status["captured_at"], "expiresAt": status["captured_at"] + 300,
            "summary": {"fault": fault, "fix": classifier + " Native task not yet verified."},
            "reasons": [fault, classifier, "Native task not yet verified or bound; recovery and native execution remain unverified."],
            "stages": [{"key": "pre-admission-fault", "label": "Known-good admission", "state": "blocked" if denials else "unknown", "reason": fault},
                       {"key": "pre-admission-classifier", "label": "Classifier admission", "state": "blocked" if phase == "suppressed" else "unknown", "reason": classifier}],
            "telemetry": {"state": "incomplete", "checks": []}, "completeDemoProof": False}


def recovery_view(activity, snapshot_path="/data/recovery.json", profile_path="/profile/profile.json",
                  admission_status_path="/data/admission-status.json", admission_profile_path="/profile/admission.json", now=None):
    full = read_view(snapshot_path, profile_path, activity, now)
    if full.get("binding", {}).get("taskId"):
        return full
    return pre_admission_view(admission_status_path, admission_profile_path, now) or full


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, code, body, mime="application/json"):
        if mime == "application/json":
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def received(self, path):
        with self.server.opener.open(Request(self.server.upstream + path), timeout=8) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Received activity exceeds transport limit")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("Invalid received activity")
        return value

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == "/healthz":
                return self.reply(200, {"ok": True, "readOnly": True})
            if path == "/api/state":
                value = merge_observed_traces(self.received("/api/state"), observed_archive())
                value.pop("onboarding", None)
                value["invocation"] = {"status": "idle"}
                value["sessionActivity"] = None
                value["recovery"] = recovery_view(value)
                value["runtime"] = {"readOnlyViewer": True, "substrateInstalled": True,
                                    "demoMode": "connected", "executionTargets": [], "scenarios": [],
                                    "label": "Kyverno recovery · received shared-collector OTel activity",
                                    "promptHelp": "Observe the native Kyverno agent through its existing client."}
                return self.reply(200, value)
            if path == "/api/logs":
                params = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                if set(params) - {"traceId", "service"} or any(len(v) != 1 for v in params.values()):
                    return self.reply(400, {"error": "Invalid log filter"})
                trace = params.get("traceId", [""])[0]
                service = params.get("service", [""])[0]
                if (trace and not re.fullmatch("[0-9a-f]{32}", trace)) or len(service) > 128:
                    return self.reply(400, {"error": "Invalid log filter"})
                current = self.received("/api/logs?" + urlencode({"traceId": trace, "service": service}))
                return self.reply(200, merge_observed_logs(current, observed_archive(), trace, service))
            if path in ASSETS:
                filename, mime = ASSETS[path]
                return self.reply(200, (Path("/ui") / filename).read_bytes(), mime)
            return self.reply(404, {"error": "Unknown route"})
        except (OSError, ValueError, TypeError):
            return self.reply(503, {"error": "Received activity is unavailable; recovery is unverified"})

    def do_POST(self):
        self.close_connection = True
        return self.reply(403, {"error": "Read-only viewer"})


def main():
    upstream = os.environ["OTEL_VIEWER_URL"].rstrip("/")
    parsed = urlsplit(upstream)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Require the fixed collector viewer origin")
    server = ThreadingHTTPServer(("0.0.0.0", 8787), Handler)
    server.daemon_threads = True
    server.upstream, server.opener = upstream, build_opener(NoRedirect())
    server.serve_forever()


if __name__ == "__main__":
    main()
