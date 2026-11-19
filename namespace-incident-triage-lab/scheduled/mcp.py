"""Serve admitted-incident inspection, assigned GitLab handoff and feedback."""
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit

from scanner import DAY, Kube, collect, policy, request, rule_signature

TRIAGE = "triage_application_incident"
INSPECT = "inspect_application"
TICKET = "ensure_gitlab_incident_issue"
PROPOSE = "propose_ignore"
ID = re.compile(r"[a-f0-9]{24}")
RATIONALES = ["expected_application_behavior", "known_non_actionable_signal", "transient_controller_noise"]
DESCRIPTIONS = {
    TRIAGE: "Read Kubernetes evidence and record the assigned ticket in one call for an admitted incident.",
    INSPECT: "Read current Deployment readiness and the bounded evidence for an admitted incident.",
    TICKET: "Preview or ensure one assigned confidential GitLab issue for an admitted incident.",
    PROPOSE: "Record an optional ignore recommendation for one cited signal. Human approval is required.",
}


def application_context(incident_id):
    if not isinstance(incident_id, str) or not ID.fullmatch(incident_id):
        raise ValueError("Invalid incident ID")
    kube = Kube()
    cfg = policy()
    _, state = kube.configmap(os.environ["STATE_NAME"], "state.json")
    item = state["dispatches"].get(incident_id)
    if (not item or state.get("active") != incident_id or int(time()) - item["admitted_at"] >= DAY
            or item["namespace"] != kube.namespace or item["application"] != cfg["application"]
            or item["cluster"] != cfg["cluster"]):
        raise ValueError("Incident is outside the current admitted application scope")
    return kube, cfg, item


def update_outcomes(kube, incident_id, change):
    for _ in range(5):
        obj, all_outcomes = kube.configmap(os.environ["OUTCOMES_NAME"], "outcomes.json")
        cutoff = int(time()) - 7 * DAY
        all_outcomes = {key: item for key, item in all_outcomes.items() if item["updated_at"] >= cutoff}
        record = all_outcomes.setdefault(incident_id, {})
        result = change(record)
        record["updated_at"] = int(time())
        try:
            kube.save(obj, "outcomes.json", all_outcomes)
            return result
        except HTTPError as error:
            if error.code != 409:
                raise
    raise ValueError("Concurrent outcome updates exceeded retry limit")


def preview(item, assignee):
    return {"status": "preview", "incident_id": item["incident_id"], "assignee_ids": [assignee]}


def gitlab_issue(kube, item, assignee, payload):
    origin = os.environ["GITLAB_URL"]
    project = int(os.environ["GITLAB_PROJECT_ID"])
    target = urlsplit(origin)
    if (target.scheme != "https" or not target.hostname or target.username or target.password
            or target.path or target.query or target.fragment or project < 1):
        raise ValueError("Invalid configured GitLab destination")
    incident_id = item["incident_id"]
    label = "incident-" + incident_id
    url = f"{origin}/api/v4/projects/{project}/issues"
    headers = {"Authorization": "Bearer " + os.environ["GITLAB_TOKEN"], "Accept": "application/json"}
    params = urlencode({"labels": label, "per_page": 2})

    def claim(record):
        previous = record.get("ticket")
        if previous and previous["status"] in ("writing", "created", "existing"):
            return False
        record["ticket"] = {"status": "writing"}
        return True

    def lookup():
        matches = json.loads(request(f"{url}?{params}", headers=headers))
        if not isinstance(matches, list) or len(matches) > 1:
            raise ValueError("Ambiguous GitLab issue lookup")
        return matches

    matches = lookup()
    if matches:
        issue, result = matches[0], "existing"
    else:
        if not update_outcomes(kube, incident_id, claim):
            matches = lookup()
            if not matches:
                raise ValueError("Pending GitLab write requires operator reconciliation")
            issue, result = matches[0], "existing"
        else:
            issue = json.loads(request(url, method="POST", headers=headers, document=payload))
            result = "created"
    iid = issue["iid"]
    if type(iid) is not int or iid < 1:
        raise ValueError("Invalid GitLab issue number")
    verified = json.loads(request(f"{url}/{iid}", headers=headers))
    if (verified["iid"] != iid or verified["project_id"] != project or verified["confidential"] is not True
            or assignee not in {user["id"] for user in verified["assignees"]}
            or label not in verified["labels"] or not verified["web_url"].startswith(origin + "/")):
        raise ValueError("GitLab issue read-back mismatch")
    return {**preview(item, assignee), "status": result, "iid": iid, "url": verified["web_url"]}


def call_tool(tool, args):
    expected = {"incident_id", "signature", "rationale"} if tool == PROPOSE else {"incident_id"}
    if tool not in DESCRIPTIONS or not isinstance(args, dict) or set(args) != expected:
        raise ValueError("Invalid tool arguments")
    incident_id = args["incident_id"]
    kube, cfg, item = application_context(incident_id)
    if tool == TRIAGE:
        try:
            inspection = inspect(kube, cfg, item)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            inspection = {"status": "unavailable"}
        ticket = ticket_receipt(kube, item)
        return {"inspection": inspection, "ticket": ticket}
    if tool == INSPECT:
        return inspect(kube, cfg, item)
    if tool == PROPOSE:
        signature, rationale = args["signature"], args["rationale"]
        if (signature not in item["signals"] or not signature.startswith(("log:", "event:"))
                or rationale not in RATIONALES or item["health"]["state"] != "ready"):
            raise ValueError("Proposal must name an admitted log or event from a ready application")
        deployment = kube.get("apis/apps/v1", f"deployments/{cfg['deployment']}")
        desired = deployment["spec"].get("replicas", 1)
        status = deployment.get("status", {})
        if (desired < 1 or status.get("availableReplicas", 0) < desired
                or status.get("observedGeneration", 0) < deployment["metadata"]["generation"]):
            raise ValueError("Ignore proposals require fresh, fully available Deployment state")
        suggestion = {"signature": signature, "rationale": rationale, "status": "pending-review"}

        def record_proposal(record):
            return record.setdefault("suggestion", suggestion)

        return update_outcomes(kube, incident_id, record_proposal)
    return ticket_receipt(kube, item)


def inspect(kube, cfg, item):
    now = int(time())
    health, current = collect(kube, cfg, now - cfg["max_gap_seconds"], now)
    matches = {key: timestamp for key, timestamp in current.items() if key in item["signals"]}
    named_rules = {key: rule["id"] for rule in cfg["log_rules"]
                   if (key := "log:" + rule_signature(rule["id"])) in item["signals"]}
    return {"admission": item, "deployment": cfg["deployment"], "health_now": health,
            "last_seen": matches, "named_log_rules": named_rules}


def ticket_receipt(kube, item):
    incident_id = item["incident_id"]
    assignee = int(os.environ["GITLAB_ASSIGNEE_ID"])
    if assignee < 1:
        raise ValueError("Invalid GitLab assignee")
    mode = os.environ["TICKET_MODE"]
    if mode == "preview":
        receipt = preview(item, assignee)
    elif mode == "gitlab":
        label = "incident-" + incident_id
        target = f"{item['namespace']}/{item['application']}"
        facts = "\n".join(f"- `{signal}`" for signal in item["signals"])
        field = os.environ.get("GITLAB_ASSIGNMENT_FIELD", "assignee_id")
        if field not in {"assignee_id", "assignee_ids"}:
            raise ValueError("Unsupported GitLab assignment field")
        assignment = {field: [assignee] if field == "assignee_ids" else assignee}
        payload = {"title": f"Application incident: {target}", "confidential": True,
                   "labels": f"namespace-triage,{label}", **assignment,
                   "description": f"Application: {target}\nHealth: {item['health']['state']}\n\n"
                                  f"Observed signals\n{facts}\n\nInvestigate the source logs and events."}
        receipt = gitlab_issue(kube, item, assignee, payload)
    else:
        raise ValueError("Invalid ticket mode")

    def record_ticket(record):
        record["ticket"] = receipt
        return receipt

    return update_outcomes(kube, incident_id, record_ticket)


def tools():
    definitions = []
    for name, description in DESCRIPTIONS.items():
        properties = {"incident_id": {"type": "string", "pattern": "^[a-f0-9]{24}$"}}
        if name == PROPOSE:
            properties["signature"] = {"type": "string"}
            properties["rationale"] = {"type": "string", "enum": RATIONALES}
        definitions.append({"name": name, "description": description,
                            "inputSchema": {"type": "object", "additionalProperties": False,
                                            "required": list(properties), "properties": properties}})
    return {"tools": definitions}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, status, document=None):
        raw = b"" if document is None else json.dumps(document).encode()
        self.send_response(status)
        if raw:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply(200 if self.path == "/healthz" else 405)

    def do_POST(self):
        secret = os.environ.get("MCP_SHARED_KEY", "")
        if not secret or not hmac.compare_digest(self.headers.get("X-Incident-MCP-Key", ""), secret):
            return self.reply(401)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if self.path != "/mcp" or not 0 < size <= 16_384:
                return self.reply(400)
            self.connection.settimeout(5)
            req = json.loads(self.rfile.read(size))
            method, params = req["method"], req.get("params", {})
            if req.get("jsonrpc") != "2.0" or not isinstance(params, dict):
                return self.reply(400)
        except (OSError, ValueError, TypeError, KeyError):
            return self.reply(400)
        response = {"jsonrpc": "2.0", "id": req.get("id")}
        if method == "initialize":
            version = params.get("protocolVersion")
            result = {"protocolVersion": version if version in ("2025-03-26", "2025-06-18", "2025-11-25")
                      else "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "application-incident", "version": "1.0"}}
        elif method == "notifications/initialized":
            return self.reply(202)
        elif method == "tools/list":
            result = tools()
        elif method == "ping":
            result = {}
        elif method == "tools/call":
            error = False
            name = params.get("name")
            try:
                args = params.get("arguments", {})
                output = call_tool(name, args)
                audit = {"tool": name, "status": "ok", "incident_id": args["incident_id"]}
                if name == TRIAGE:
                    audit["inspection"] = output["inspection"].get("status", "verified")
                    audit["ticket"] = output["ticket"]["status"]
                print(json.dumps(audit), flush=True)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as problem:
                error = True
                reason = {
                    "Invalid incident ID": "Copy the exact incident_id from the incoming JSON.",
                    "Invalid tool arguments": "Provide only the arguments in the tool schema.",
                    "Incident is outside the current admitted application scope":
                        "Use the exact incoming incident_id. The specified incident is not active.",
                }.get(str(problem), "Operation failed. Check admission, source access and prior issue state.")
                output = {"error": reason}
                audit = {"status": "application-tool-error", "class": type(problem).__name__, "detail": reason}
                if isinstance(name, str) and name in DESCRIPTIONS:
                    audit["tool"] = name
                if isinstance(problem, HTTPError):
                    audit["http_status"] = problem.code
                print(json.dumps(audit), flush=True)
            result = {"isError": error, "content": [{"type": "text", "text": json.dumps(output)}]}
        else:
            response["error"] = {"code": -32601, "message": "Method not found"}
            return self.reply(200, response)
        response["result"] = result
        self.reply(200, response)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8084), Handler).serve_forever()
