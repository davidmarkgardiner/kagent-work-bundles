#!/usr/bin/env python3
"""Run actual agent workflows through the HTTPS front door and verify native OTel."""
import argparse
import json
import os
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

CASES = {
    "triage": ("Call get_kubernetes_workloads, query_grafana_alerts, then get_gitlab_issue. Explain the simulated incident without changing anything.", ["get_kubernetes_workloads", "query_grafana_alerts", "get_gitlab_issue"]),
    "sdlc": ("Call get_gitlab_issue, get_gitlab_pipeline, then review_change. Do not write, deploy, or trigger anything.", ["get_gitlab_issue", "get_gitlab_pipeline", "review_change"]),
    "identity-isolation": ("Call read_team_a_resource, attempt_cross_team_resource, then read_team_b_resource. Explain the simulated policy results without claiming real Entra validation.", ["read_team_a_resource", "attempt_cross_team_resource", "read_team_b_resource"]),
    "inventory": ("Call get_inventory_status, then get_recent_alerts. Summarize the simulated inventory health.", ["get_inventory_status", "get_recent_alerts"]),
    "change-review": ("Call get_inventory_status, then review_change. Explain the simulated decision. Do not deploy anything.", ["get_inventory_status", "review_change"]),
    "dependency-failure": ("Call check_dependency once. Explain the intentional simulated failure. Do not retry.", ["check_dependency"]),
}


def server_tool_pairs(spans):
    return {(s["service"], s["attributes"].get("gen_ai.tool.name") or s["attributes"].get("mcp.tool.name") or s["attributes"].get("tool.name"))
            for s in spans if s.get("toolExecution") in {"server", "kagent-tools-internal"} and s["status"] == "ok"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--expect-tool", action="append", default=[])
    parser.add_argument("--tool-service")
    parser.add_argument("--expect-mcp", action="append", default=[], metavar="SERVICE:TOOL")
    parser.add_argument("--runtime")
    parser.add_argument("--execution-mode", choices=["substrate", "standalone"], default="substrate")
    parser.add_argument("--context")
    parser.add_argument("--namespace", default="agent-flow-demo")
    args = parser.parse_args()
    custom = args.prompt_file is not None
    if args.expect_mcp:
        if not custom or args.expect_tool or args.tool_service or any(value.count(":") != 1 for value in args.expect_mcp):
            parser.error("Use --prompt-file and SERVICE:TOOL pairs without the single-server options")
        expected_pairs = [tuple(value.split(":", 1)) for value in args.expect_mcp]
    else:
        if custom != bool(args.expect_tool) or custom != bool(args.tool_service):
            parser.error("Connected verification requires --prompt-file and expected server tools")
        expected_pairs = [(args.tool_service, name) for name in args.expect_tool]
    if custom and args.case != "all":
        parser.error("Use a custom prompt or a fixture case, not both")
    custom_prompt = args.prompt_file.read_text().strip() if custom else None
    if custom and not custom_prompt:
        parser.error("The approved prompt file is empty")
    standalone = args.execution_mode == "standalone"
    origin = args.url.rstrip("/")
    if urllib.parse.urlparse(origin).scheme != "https":
        parser.error("Verification requires HTTPS; certificate verification cannot be disabled")
    context = ssl.create_default_context(cafile=str(args.ca) if args.ca else None)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())
    headers = {"Content-Type": "application/json", "Origin": origin}
    if token := os.getenv("FLOW_AUTH_BEARER"):
        headers["Authorization"] = "Bearer " + token

    def request(path, payload=None, extra=None):
        req = urllib.request.Request(origin + path, None if payload is None else json.dumps(payload).encode(),
                                     {**headers, **(extra or {})})
        try:
            with opener.open(req, timeout=15) as response:
                return response.status, json.loads(response.read(8 * 1024 * 1024))
        except urllib.error.HTTPError as error:
            code = error.code
            with error:
                error.read(65536)
            return code, None

    assert request("/healthz")[0] == 200, "HTTPS liveness failed"
    assert request("/v1/traces", {"resourceSpans": []})[0] == 404, "OTLP traces are exposed at ingress"
    assert request("/v1/logs", {"resourceLogs": []})[0] == 404, "OTLP logs are exposed at ingress"
    assert request("/api/invoke", {"prompt": ""})[0] == 400, "Empty prompt accepted"
    assert request("/api/invoke", {"prompt": "invalid origin"}, {"Origin": "https://untrusted.invalid"})[0] == 403, "Cross-origin submission accepted"
    _, initial_state = request("/api/state")
    if (initial_state["runtime"]["demoMode"] in {"connected", "live-tools"}) != custom:
        parser.error("Use a reviewed custom prompt for connected mode and fixture cases for the bundled demo")
    cases = {"connected": (custom_prompt, [tool for _, tool in expected_pairs])} if custom else CASES
    tool_service = args.tool_service if custom else "flow-demo-tools"
    expected_services = {service for service, _ in expected_pairs} if custom else {tool_service}
    results = []
    for name, (prompt, tools) in cases.items():
        if args.case != "all" and name != args.case:
            continue
        invocation_payload = {"prompt": prompt if custom else f"DEMO_WORKFLOW={name}. {prompt}"}
        if args.runtime:
            invocation_payload["runtime"] = args.runtime
        code, accepted = request("/api/invoke", invocation_payload)
        assert code == 202, f"{name}: invocation not accepted"
        trace = accepted["traceId"]
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            _, state = request("/api/state")
            invocation = state["invocation"]
            if invocation.get("traceId") != trace:
                raise AssertionError("Another caller replaced this verification run")
            if invocation["status"] == "failed":
                raise AssertionError(f"{name}: agent invocation failed")
            activity = state.get("sessionActivity") or {}
            selected = next((t for t in state["traces"] if t["traceId"] == trace), None)
            related = [selected] if standalone and selected else [t for t in state["traces"] if t["traceId"] in activity.get("traceIds", [])]
            spans = [s for t in related for s in t["spans"]]
            worker = {s["name"] for s in spans if s["service"] in {"atelet", "ateom-gvisor"}}
            successful_pairs = server_tool_pairs(spans)
            server_tools = {tool for service, tool in successful_pairs if service in expected_services}
            expected_observed = set(expected_pairs) <= successful_pairs if custom else set(tools) <= {s["attributes"].get("gen_ai.tool.name") for s in spans if s["service"] == tool_service}
            states = [e["state"] for e in activity.get("states", [])]
            components = selected["components"] if standalone and selected else activity.get("components", [])
            expected_components = {"client", "kagent", "agentgateway", "model", "mcp"} | (set() if standalone else {"substrate", "worker", "actor"})
            lifecycle_ready = standalone or (states and states[-1] == "suspended" and any("CheckpointWorkload" in n for n in worker) and any("RestoreWorkload" in n for n in worker))
            if (invocation["status"] == "completed" and selected and expected_observed
                    and lifecycle_ready and expected_components <= set(components)):
                break
            time.sleep(0.5)
        else:
            raise AssertionError(f"{name}: native workflow/lifecycle evidence did not arrive before the deadline")
        assert expected_components <= set(components), f"{name}: missing components"
        if standalone:
            assert not {"substrate", "worker", "actor"} & set(components), "Standalone run contains Substrate activity"
            assert not activity and not invocation.get("actorName"), "Standalone run acquired an actor"
            assert any(s["service"] == "flow-standalone-kagent" for s in spans), "Native standalone runtime span missing"
            assert invocation.get("executionMode") == "standalone", "Wrong runtime executed"
        else:
            assert any("RestoreWorkload" in n for n in worker), "Worker restore is missing"
        fixture_spans = [s for s in spans if s["service"] in expected_services]
        if custom:
            assert not any(s["attributes"].get("flow.simulated") is True for s in fixture_spans), "Connected proof contains simulated tool data"
        else:
            assert all(s["attributes"].get("flow.simulated") is True for s in fixture_spans), "Fixture tools are not labelled"
        if not custom:
            for server_span in fixture_spans:
                tool_name = server_span["attributes"].get("gen_ai.tool.name")
                if tool_name in tools and tool_name not in {"check_dependency", "attempt_cross_team_resource"}:
                    assert server_span["status"] == "ok", "A required fixture tool failed"
        failed = [s for s in fixture_spans if s["attributes"].get("gen_ai.tool.name") == "check_dependency" and s["status"] == "error"]
        if name == "identity-isolation":
            decisions = {(s["attributes"].get("flow.security.subject"), s["attributes"].get("flow.security.resource"), s["attributes"].get("flow.security.decision")) for s in fixture_spans}
            assert {("agent-a", "team-a", "allow"), ("agent-a", "team-b", "deny"), ("agent-b", "team-b", "allow")} <= decisions
            assert any(s["status"] == "error" and s["attributes"].get("flow.security.decision") == "deny" for s in fixture_spans)
        if name == "dependency-failure":
            assert failed, "Intentional dependency failure was not exported as an error"
        _, log_data = request("/api/logs")
        if not standalone:
            assert any(r["event"] == "ate.actor.state_changed" and r["attributes"].get("ate.actor.name") == activity["actorName"]
                       for r in log_data["logs"]), "Native actor lifecycle log missing"
        if state["runtime"]["demoMode"] == "fixture":
            assert "SIMULATED_WORKFLOW_COMPLETE" in invocation["text"], "Fixture result is not labelled"
            assert selected["costUsd"] is None, "Fixture transaction gained a billed cost"
        results.append({"workflow": name, "mode": state["runtime"]["demoMode"], "traceId": trace,
                        "sessionId": invocation["sessionId"], "status": invocation["status"],
                        "elapsedSeconds": round(invocation["finishedAt"] - invocation["startedAt"], 3),
                        "requestSpanCount": selected["spanCount"], "relatedTraceIds": [trace] if standalone else activity["traceIds"], "executionMode": args.execution_mode, "runtime": args.runtime,
                        "observedComponents": components, "tools": tools, "toolService": tool_service, "expectedServerTools": expected_pairs if custom else [],
                        "actorStates": states, "workerOperations": sorted(worker),
                        "inputTokens": selected["inputTokens"], "outputTokens": selected["outputTokens"],
                        "modelCallCount": len(selected["modelCalls"]), "billedUsd": selected["costUsd"],
                        "intentionalToolErrorObserved": bool(failed)})
        print(f"PASS {name}: HTTPS, model/tool traffic, " + ("standalone native Deployment, no actor activity" if standalone else "worker restore/checkpoint, actor suspended"), flush=True)
    result = {"url": origin, "tlsCertificateVerified": True, "externalOtlpBlocked": True,
              "crossOriginBlocked": True, "workflows": results, "browserVisualRecheck": False,
              "aksIstioRuntimeTested": False, "networkPolicyEnforcementTested": False}
    if args.context:
        import subprocess

        def get(resource):
            return json.loads(subprocess.run(["kubectl", "--context", args.context, "-n", args.namespace,
                                              "get", resource, "-o", "json"], check=True, text=True, capture_output=True).stdout)["items"]

        pods, services, endpoints = get("pods"), get("services"), get("endpointslices")
        addresses = {a["ip"] for p in pods for a in p["status"].get("podIPs", [])}
        assert all(s["spec"]["type"] == "ClusterIP" and s["spec"].get("selector") for s in services), "External or manually bridged service found"
        assert all(a in addresses for ep in endpoints for entry in ep.get("endpoints", []) for a in entry["addresses"]), "A service endpoint is outside this namespace's pods"
        workloads = get("deployments")
        assert not any(p["spec"].get("hostNetwork") for p in pods), "Host network dependency found"
        serialized = json.dumps(workloads)
        assert not any(value in serialized for value in ["host.docker.internal", "18082", "127.0.0.1:18083"]), "Host bridge dependency found"
        result["singleClusterRuntime"] = {"namespace": args.namespace, "serviceEndpointsArePods": True,
                                           "servicesAreInternal": True, "hostBridgeDependencies": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("Saved verification receipt to " + str(args.output))


if __name__ == "__main__":
    main()
