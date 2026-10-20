"""Probe approved MCP front doors with existing identities; emit metadata-only OTLP."""
import argparse
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from workflow_demo import export_event


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def load_plan(path):
    plan = json.loads(path.read_text())
    cases = plan.get("cases", [])
    if not isinstance(cases, list) or not 2 <= len(cases) <= 12:
        raise ValueError("Provide two to twelve approved cases")
    identities, resources, names, statuses = set(), set(), set(), set()
    for case in cases:
        for field in ("name", "subject", "resource", "metric"):
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", case[field]):
                raise ValueError("Use bounded public aliases and a single unlabelled metric name")
        if case["name"] in names:
            raise ValueError("Case names must be unique")
        for field in ("url", "metricsUrl"):
            url = urllib.parse.urlparse(case[field])
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError("Require approved HTTPS URLs without embedded credentials or query strings")
        for field in ("tokenEnv", "metricsTokenEnv"):
            name = case.get(field)
            if name is not None and not re.fullmatch(r"[A-Z][A-Z0-9_]{1,100}", name):
                raise ValueError("Credentials must be environment variable references")
        if case["expectedStatus"] not in (200, 401, 403):
            raise ValueError("Expected status must be 200, 401, or 403")
        identities.add(case["subject"])
        resources.add(case["resource"])
        names.add(case["name"])
        statuses.add(case["expectedStatus"])
    if len(identities) < 2 or len(resources) < 2 or 200 not in statuses or not statuses.intersection({401, 403}):
        raise ValueError("Include multiple identities/resources, an allowed call, and a denied call")
    return cases


def token_headers(name):
    return {"Authorization": "Bearer " + os.environ[name]} if name else {}


def counter(opener, case):
    request = urllib.request.Request(case["metricsUrl"], headers=token_headers(case.get("metricsTokenEnv")))
    with opener.open(request, timeout=15) as response:
        text = response.read(1024 * 1024).decode()
    values = re.findall(r"^" + re.escape(case["metric"]) + r"\s+([0-9]+(?:\.0+)?)\s*$", text, re.MULTILINE)
    if len(values) != 1:
        raise ValueError("Require exactly one unlabelled backend request counter")
    return int(float(values[0]))


def run(cases, opener, emit=export_event):
    for case in cases:
        for field in ("tokenEnv", "metricsTokenEnv"):
            if case.get(field) and not os.getenv(case[field]):
                raise ValueError("A required credential environment variable is missing")
    results = []
    for case in cases:
        start, trace, span = time.time_ns(), uuid.uuid4().hex, uuid.uuid4().hex[:16]
        before = after = observed = None
        response_valid, passed, error = False, False, None
        try:
            before = counter(opener, case)
            payload = {"jsonrpc": "2.0", "id": trace, "method": "initialize", "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "agent-flow-isolation-probe", "version": "1.0"}}}
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                       "traceparent": f"00-{trace}-{span}-01", **token_headers(case.get("tokenEnv"))}
            request = urllib.request.Request(case["url"], json.dumps(payload).encode(), headers)
            try:
                with opener.open(request, timeout=15) as response:
                    observed = response.status
                    data = response.read(1024 * 1024).decode()
                if data.startswith("data:"):
                    messages = [json.loads(line[5:].strip()) for line in data.splitlines()
                                if line.startswith("data:") and line[5:].strip() != "[DONE]"]
                    message = next((m for m in messages if m.get("id") == trace), {})
                else:
                    message = json.loads(data)
                response_valid = (message.get("id") == trace and isinstance(message.get("result", {}).get("serverInfo"), dict)
                                  and isinstance(message.get("result", {}).get("protocolVersion"), str))
            except urllib.error.HTTPError as failure:
                observed = failure.code
                with failure:
                    failure.read(1024 * 1024)
            after = counter(opener, case)
            delta = after - before
            passed = observed == case["expectedStatus"] and (delta > 0 and response_valid if observed == 200 else delta == 0)
        except (OSError, ValueError, KeyError):
            error = "Request, counter, or response validation failed. Inspect private server logs."
        values = {"flow.component": "client", "flow.destination": "agentgateway", "flow.simulated": False,
                  "flow.security.subject": case["subject"], "flow.security.resource": case["resource"],
                  "flow.security.check": case["name"], "flow.security.authority": "client HTTP response and backend counter",
                  "flow.security.expected_status": case["expectedStatus"],
                  "flow.security.decision": "probe matched" if passed else "probe failed", "http.request.method": "POST"}
        if observed is not None:
            values.update({"flow.security.observed_status": observed, "http.response.status_code": observed})
        if before is not None and after is not None:
            values["flow.security.backend_delta"] = after - before
        exported = emit("flow-client-isolation-probe", trace, span, "", "MCP access probe " + case["name"], start,
             2 if not passed or observed in (401, 403) else 1, values, kind=3)
        results.append({"case": case["name"], "subject": case["subject"], "resource": case["resource"],
                        "traceId": trace, "expectedStatus": case["expectedStatus"], "observedStatus": observed,
                        "backendRequestDelta": after - before if before is not None and after is not None else None,
                        "validInitializeResponse": response_valid, "otelExported": exported is True, "result": "PASS" if passed else "FAIL", "error": error})
        print(("PASS " if passed else "FAIL ") + case["name"], flush=True)
    return {"scope": "MCP front-door initialize probes. No tools or agents are executed.", "cases": results,
            "entraIssuerAndPolicyVerified": False, "directBackendBypassTested": False, "tokenRefreshTested": False,
            "note": "Join these client probes to native gateway decisions. Verify Entra issuer/audience/roles and direct-network denial separately."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ca", type=Path)
    args = parser.parse_args()
    try:
        cases = load_plan(args.plan)
        context = ssl.create_default_context(cafile=str(args.ca) if args.ca else None)
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())
        result = run(cases, opener)
    except (OSError, ValueError, KeyError):
        parser.exit(2, "Invalid plan, TLS input, or missing credential reference. Keep details in the private operator context.\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if any(case["result"] != "PASS" for case in result["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
