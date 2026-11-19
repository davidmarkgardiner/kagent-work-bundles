"""Bounded Kubernetes and GitLab MCP operations for the certificate lab."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import ssl
from threading import Lock
from time import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

TOOL = "ensure_gitlab_incident_issue"
READ_TOOL = "get_certificate_health"
LOCK = Lock()
RECENT_TICKET = {}
SA = Path("/var/run/secrets/kubernetes.io/serviceaccount")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def request_json(url, token, *, context=None, body=None):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    opener = build_opener(NoRedirect(), HTTPSHandler(context=context))
    with opener.open(Request(url, data=data, headers=headers), timeout=15) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError("Response exceeds limit")
    return json.loads(raw)


def certificate_state():
    cluster = os.environ["CLUSTER_ID"]
    namespace = os.environ["APP_NAMESPACE"]
    name = os.environ["CERTIFICATE_NAME"]
    api = f"https://kubernetes.default.svc/apis/cert-manager.io/v1/namespaces/{namespace}"
    context = ssl.create_default_context(cafile=SA / "ca.crt")
    token = (SA / "token").read_text().strip()
    cert = request_json(f"{api}/certificates/{name}", token, context=context)
    source = cert["spec"]["issuerRef"]
    issuer = source["name"]
    if (source.get("kind", "Issuer") != "Issuer"
            or source.get("group", "cert-manager.io") != "cert-manager.io"
            or not re.fullmatch(r"[a-z0-9-]{1,63}", issuer)):
        raise ValueError("Unsupported issuer")
    ready = next((c["status"] for c in cert.get("status", {}).get("conditions", [])
                  if c.get("type") == "Ready"), "Unknown")
    fingerprint = hashlib.sha256(
        f"{cluster}/{namespace}/{cert['metadata']['uid']}/IssuerNotFound\n".encode()
    ).hexdigest()[:24]
    exists = True
    try:
        request_json(f"{api}/issuers/{issuer}", token, context=context)
    except HTTPError as error:
        with error:
            if error.code != 404:
                raise
        exists = False
    facts = {"cluster": cluster, "namespace": namespace, "certificate": name,
             "issuer": issuer, "issuer_exists": exists, "ready": ready, "incident_id": fingerprint}
    marker = cert["metadata"].get("annotations", {}).get("triage.lab/read-proof", "")
    if re.fullmatch(r"[0-9a-f]{16}", marker):
        facts["certificate_marker"] = marker
    return facts


def ensure_issue():
    with LOCK:
        facts = certificate_state()
        if facts["issuer_exists"] or facts["ready"] != "False":
            raise ValueError("The configured Certificate is outside the supported fault state")
        incident_id = facts["incident_id"]
        cluster, namespace, name, issuer = (facts[key] for key in ("cluster", "namespace", "certificate", "issuer"))
        assignee = int(os.environ["GITLAB_ASSIGNEE_ID"])
        if assignee < 1:
            raise ValueError("Invalid configured assignee")
        label = f"incident-{incident_id}"
        payload = {
            "title": f"[Lab] Certificate issuance blocked: {namespace}/{name}",
            "confidential": True,
            "labels": f"namespace-triage,lab,{label}",
            "assignee_ids": [assignee],
            "description": (
                f"## Confirmed source state\nThe Certificate is unready and its Issuer is missing.\n"
                f"- Cluster: {cluster}\n- Namespace: {namespace}\n- Certificate: {name}\n"
                f"- Issuer: {issuer}\n\n"
                "## Owner action\nRestore the intended Issuer reference through GitOps. "
                "Check Certificate Ready=True and validate application TLS.\n"
            ),
        }
        mode = os.environ["TICKET_MODE"]
        receipt = {"incident_id": incident_id, "assignee_ids": [assignee]}
        if mode == "preview":
            return {**receipt, "status": "preview", "title": payload["title"]}
        if mode != "gitlab" or not os.environ.get("MCP_SHARED_KEY"):
            raise ValueError("Live mode requires authenticated MCP access")
        origin = os.environ["GITLAB_URL"]
        project = int(os.environ["GITLAB_PROJECT_ID"])
        target = urlsplit(origin)
        if (target.scheme != "https" or not target.hostname or target.username or target.password
                or target.path or target.query or target.fragment or project < 1):
            raise ValueError("Invalid GitLab destination")
        token = os.environ["GITLAB_TOKEN"]
        issues_url = f"{origin}/api/v4/projects/{project}/issues"
        matches = request_json(f"{issues_url}?{urlencode({'labels': label, 'per_page': 2})}", token)
        if not isinstance(matches, list) or len(matches) > 1:
            raise ValueError("Ambiguous GitLab issue lookup")
        if matches:
            iid, status = matches[0]["iid"], "existing"
        else:
            iid, status = request_json(issues_url, token, body=payload)["iid"], "created"
        if type(iid) is not int or iid < 1:
            raise ValueError("Invalid issue number")
        result = request_json(f"{issues_url}/{iid}", token)
        ids = [user["id"] for user in result["assignees"]]
        if (result["iid"] != iid or result["project_id"] != project
                or result["confidential"] is not True or assignee not in ids
                or label not in result["labels"] or not result["web_url"].startswith(f"{origin}/")):
            raise ValueError("GitLab read-back does not match the intended issue")
        return {**receipt, "status": status, "iid": iid, "url": result["web_url"], "assignee_ids": ids}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, code, payload=None):
        data = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            return self.reply(200, {"status": "ready"})
        match = re.fullmatch(r"/receipts/([a-f0-9]{24})", self.path)
        if match and os.environ.get("MCP_ROLE") != "kubernetes":
            with LOCK:
                receipt = dict(RECENT_TICKET)
            if receipt.get("incident_id") == match[1]:
                return self.reply(200, receipt)
            return self.reply(404)
        self.reply(405)

    def do_POST(self):
        read_only = os.environ.get("MCP_ROLE") == "kubernetes"
        active_tool = READ_TOOL if read_only else TOOL
        key = os.environ.get("MCP_SHARED_KEY") or ""
        if (not read_only and os.environ["TICKET_MODE"] == "gitlab" and not key
                or key and not hmac.compare_digest(self.headers.get("X-Incident-MCP-Key", ""), key)):
            return self.reply(401)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if self.path != "/mcp" or not 0 < size <= 16384:
                return self.reply(400)
            self.connection.settimeout(10)
            call = json.loads(self.rfile.read(size))
            method = call["method"]
            params = call.get("params", {})
            if not isinstance(params, dict) or call.get("jsonrpc") != "2.0":
                return self.reply(400)
        except (OSError, ValueError, TypeError, KeyError):
            return self.reply(400)
        try:
            if method == "initialize":
                version = params.get("protocolVersion")
                result = {
                    "protocolVersion": version if version in ("2025-03-26", "2025-06-18", "2025-11-25")
                    else "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": active_tool, "version": "1.0"},
                }
            elif method == "tools/list":
                result = {"tools": [{
                    "name": active_tool,
                    "description": ("Read the current Certificate and report whether its Issuer exists."
                                    if read_only else "Preview or ensure the assigned GitLab issue."),
                    "inputSchema": {"type": "object", "additionalProperties": False,
                                    "properties": {}},
                }]}
            elif method == "tools/call":
                if params.get("name") != active_tool:
                    raise ValueError("Invalid tool")
                if params.get("arguments", {}) != {}:
                    raise ValueError("This tool takes no arguments")
                receipt = certificate_state() if read_only else ensure_issue()
                if not read_only:
                    with LOCK:
                        RECENT_TICKET.update(
                            incident_id=receipt["incident_id"], status=receipt["status"], recorded_at=int(time())
                        )
                audit = {k: v for k, v in receipt.items() if k != "certificate_marker"}
                print(json.dumps({"tool": active_tool, **audit}), flush=True)
                result = {"content": [{"type": "text", "text": json.dumps(receipt)}], "isError": False}
            elif method == "ping":
                result = {}
            elif method == "notifications/initialized":
                return self.reply(202)
            else:
                return self.reply(200, {"jsonrpc": "2.0", "id": call.get("id"),
                                        "error": {"code": -32601, "message": "Method not found"}})
        except (OSError, ValueError, TypeError, KeyError):
            print(json.dumps({"tool": active_tool, "status": "error"}), flush=True)
            result = {"content": [{"type": "text", "text": "Operation failed. Check source, access and prior issue state."}],
                      "isError": True}
        self.reply(200, {"jsonrpc": "2.0", "id": call.get("id"), "result": result})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8084), Handler).serve_forever()
