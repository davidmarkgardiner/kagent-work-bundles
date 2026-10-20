#!/usr/bin/env python3
"""Offline source/chart checks. Does not claim an AKS or Istio runtime test."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import yaml


def main():
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(root), "-p", "test_*.py", "-q"], check=True)
    subprocess.run(["node", "--check", str(root / "ui/app.js")], check=True)
    subprocess.run(["helm", "lint", str(root / "deploy/chart")], check=True)
    source = (root / "deploy/values/aks-istio.yaml.example").read_text()
    samples = {
        "{{INTERNAL_REGISTRY}}": "registry.example.invalid",
        "{{REVIEWED_IMAGE_TAG}}": "reviewed", "{{REVIEWED_IMAGE_DIGEST}}": "sha256:" + "a" * 64,
        "{{DEMO_FQDN}}": "flow.example.invalid", "{{EXISTING_TLS_SECRET}}": "existing-demo-tls",
        "{{APPROVED_WORKERPOOL}}": "kagent-default", "{{APPROVED_SNAPSHOT_LOCATION}}": "s3://approved-demo/",
        "{{APPROVED_DEMO_USER_CONTEXT}}": "demo-partition",
    }
    for key, value in samples.items():
        source = source.replace(key, value)
    assert "{{" not in source, "Unrecognised work input"
    with tempfile.TemporaryDirectory() as temporary:
        operator = Path(temporary) / "operator.yaml"
        operator.write_text(source)
        profiles = [root / "deploy/values/local.yaml", operator]
        for profile in profiles:
            rendered = subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "-n", "agent-flow-demo", "-f", str(profile)],
                                      text=True, capture_output=True, check=True).stdout
            docs = [d for d in yaml.safe_load_all(rendered) if d]
            assert not any(s in rendered for s in ["host.docker.internal", "EndpointSlice", "127.0.0.1:18083", "18082"])
            for resource in docs:
                assert resource["metadata"].get("namespace") in {"agent-flow-demo", "kagent", "aks-istio-ingress"}
                if resource["kind"] == "Deployment":
                    pod = resource["spec"]["template"]["spec"]
                    assert pod["automountServiceAccountToken"] is False
                    assert not pod.get("hostNetwork")
                    assert all("hostPath" not in volume for volume in pod.get("volumes", []))
                if resource["kind"] == "Service":
                    assert resource["spec"].get("selector") and resource["spec"].get("type", "ClusterIP") == "ClusterIP"
            if profile == operator:
                gateway = next(d for d in docs if d["kind"] == "Gateway")
                assert gateway["metadata"]["namespace"] == "aks-istio-ingress"
                assert gateway["spec"]["selector"]["istio"] == "aks-istio-ingressgateway-internal"
                assert gateway["spec"]["servers"][1]["tls"]["credentialName"] == "existing-demo-tls"
                vs = next(d for d in docs if d["kind"] == "VirtualService")
                paths = {match["uri"]["exact"] for route in vs["spec"]["http"] for match in route["match"]}
                assert {"/", "/api/invoke", "/api/state", "/api/logs"} <= paths
                assert not {"/v1/traces", "/v1/logs"} & paths
                assert not any(d["kind"] == "Deployment" and d["metadata"]["name"] == "flow-https" for d in docs)
        existing = (root / "deploy/values/existing-agent-istio.yaml.example").read_text()
        existing_samples = {**samples, "{{EXISTING_READ_ONLY_AGENT}}": "existing-reader",
                            "{{EXISTING_GATEWAY_NAMESPACE_AND_NAME}}": "aks-istio-ingress/current-gateway"}
        for key, value in existing_samples.items():
            existing = existing.replace(key, value)
        assert "{{" not in existing
        operator.write_text(existing)
        rendered = subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "-n", "agent-flow-demo", "-f", str(operator)],
                                  text=True, capture_output=True, check=True).stdout
        docs = [d for d in yaml.safe_load_all(rendered) if d]
        assert {d["metadata"]["name"] for d in docs if d["kind"] == "Deployment"} == {"flow-dashboard", "flow-collector"}
        assert {d["metadata"]["name"] for d in docs if d["kind"] == "Service"} == {"flow-dashboard", "flow-collector"}
        assert not any(d["kind"] in {"Agent", "Harness", "AgentTemplate", "ModelConfig", "RemoteMCPServer", "Secret", "Gateway"} for d in docs)
        dashboard = next(d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"] == "flow-dashboard")
        env = {e["name"]: e.get("value") for e in dashboard["spec"]["template"]["spec"]["containers"][0]["env"]}
        assert env["AGENT_NAME"] == "existing-reader" and env["DEMO_MODE"] == "connected"
        vs = next(d for d in docs if d["kind"] == "VirtualService")
        assert vs["spec"]["gateways"] == ["aks-istio-ingress/current-gateway"]
        live_values = yaml.safe_load(existing)
        live_values["integration"] = {"mode": "bundled"}
        live_values["model"] = {"mode": "live", "name": "approved-model", "live": {"host": "provider.example.invalid:443", "existingSecret": "model-token"}}
        live_values["tools"] = {"mode": "live", "gitlab": {"project": "approved/project", "existingSecret": "gitlab-read-token"}}
        operator.write_text(yaml.safe_dump(live_values))
        live_rendered = subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "-n", "agent-flow-demo", "-f", str(operator)], text=True, capture_output=True, check=True).stdout
        live_docs = [d for d in yaml.safe_load_all(live_rendered) if d]
        deployments = {d["metadata"]["name"]: d for d in live_docs if d["kind"] == "Deployment"}
        assert set(deployments) == {"flow-dashboard", "flow-collector", "flow-gateway", "flow-kubernetes-mcp", "flow-gitlab-mcp", "flow-standalone"}
        for name, deployment in deployments.items():
            assert deployment["spec"]["template"]["spec"]["automountServiceAccountToken"] is (name == "flow-kubernetes-mcp")
        role = next(d for d in live_docs if d["kind"] == "Role")
        assert role["metadata"]["namespace"] == "agent-flow-demo"
        assert all(set(rule["verbs"]) == {"get", "list"} for rule in role["rules"])
        assert not any(d["kind"] in {"ClusterRole", "ClusterRoleBinding"} for d in live_docs)
        kubernetes_container = deployments["flow-kubernetes-mcp"]["spec"]["template"]["spec"]["containers"][0]
        assert "--read-only" in kubernetes_container["args"]
        assert "k8s" in kubernetes_container["args"]
        agent_template = next(d for d in live_docs if d["kind"] == "AgentTemplate")
        assert agent_template["spec"]["tools"][0]["mcp"]["tools"] == ["k8s_get_resources", "k8s_get_events"]
        assert "flow-workflows" not in live_rendered
        standalone_values = {**live_values, "execution": {"mode": "standalone"}}
        operator.write_text(yaml.safe_dump(standalone_values))
        standalone_render = subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "-n", "agent-flow-demo", "-f", str(operator)], text=True, capture_output=True, check=True).stdout
        standalone_docs = [d for d in yaml.safe_load_all(standalone_render) if d]
        assert not any(d["apiVersion"].startswith(("api.kagent.dev/", "ate.dev/")) for d in standalone_docs)
        native = next(d for d in standalone_docs if d["kind"] == "ConfigMap" and d["metadata"]["name"] == "flow-standalone")
        native_config = json.loads(native["data"]["agent.json"])
        assert native_config["instruction"] == agent_template["spec"]["systemPrompt"]
        assert native_config["http_tools"][0]["tools"] == ["k8s_get_resources", "k8s_get_events"]
        assert all(t["tools"] and t["require_approval"] is False for t in native_config["http_tools"])
        native_pod = next(d for d in standalone_docs if d["kind"] == "Deployment" and d["metadata"]["name"] == "flow-standalone")["spec"]["template"]["spec"]
        native_env = {v["name"] for v in native_pod["containers"][0]["env"]}
        assert not {"KAGENT_API_URL", "KAGENT_ACTOR_TOKEN", "STS_WELL_KNOWN_URI"} & native_env
        assert not native_pod["automountServiceAccountToken"]
        native_policy = next(d for d in standalone_docs if d["kind"] == "NetworkPolicy" and d["metadata"]["name"] == "flow-standalone")
        assert set(native_policy["spec"]["policyTypes"]) == {"Ingress", "Egress"}
        assert subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "--set", "tools.mode=live"], capture_output=True).returncode
        for flags in [["--set", "integration.mode=existing"], ["--set", "integration.mode=invalid"],
                      ["--set", "ingress.istio.existingGateway=invalid-reference"]]:
            assert subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), *flags], capture_output=True).returncode
        bad = subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "--set", "model.mode=unsupported"], capture_output=True)
        assert bad.returncode, "Invalid model mode was accepted"
    for script in (root / "scripts").glob("*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True)
    json.loads((root / "image-lock.json").read_text())
    print("PASS offline bundle checks. Local TLS and AKS Istio manifests render; no host runtime bridges.")


if __name__ == "__main__":
    main()
