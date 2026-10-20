#!/usr/bin/env python3
"""Read-only checks for the single-cluster demo and its ingress inputs."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="agent-flow-demo")
    parser.add_argument("--values", type=Path, required=True)
    args = parser.parse_args()
    if args.namespace in {"default", "kube-system", "kagent", "ate-system", "aks-istio-ingress", "aks-istio-system"}:
        parser.error("Use a dedicated demo application namespace, not a platform namespace")
    text = args.values.read_text()
    if re.search(r"\{\{[^}]+\}\}", text):
        parser.error("Fill every placeholder in the operator values file")
    values = yaml.safe_load(text)
    chart = Path(__file__).resolve().parents[1] / "deploy/chart"
    rendered = subprocess.run(["helm", "template", "flow-demo", str(chart), "-n", args.namespace, "-f", str(args.values)],
                              check=True, text=True, capture_output=True).stdout
    resources = [d for d in yaml.safe_load_all(rendered) if d]
    kubectl = ["kubectl", "--context", args.context]

    def get(*command):
        return json.loads(subprocess.run(kubectl + list(command) + ["-o", "json"], check=True, text=True, capture_output=True).stdout)

    versions = {v["name"] for v in get("get", "crd", "agents.api.kagent.dev")["spec"]["versions"] if v["served"]}
    if "v1alpha3" not in versions:
        parser.error("This bundle requires the installed kagent 1.x v1alpha3 API")
    agent_ns = values.get("agentNamespace", "kagent")
    integration = values.get("integration", {})
    existing = integration.get("mode", "bundled") == "existing"
    if existing:
        agent = get("-n", agent_ns, "get", "agent", integration["existingAgent"])
        if not any(c["type"] == "Ready" and c["status"] == "True" for c in agent.get("status", {}).get("conditions", [])):
            parser.error("The existing demo agent is not Ready")
        harness_name = agent["spec"].get("harnessRef", {}).get("name")
        if not harness_name:
            parser.error("Require an existing Substrate-backed Agent with a Harness reference")
        harness = get("-n", agent_ns, "get", "harness", harness_name)
        if harness["spec"].get("substrate", {}).get("workerPoolRef", {}).get("name") != values.get("workerPool", "kagent-default"):
            parser.error("The existing agent Harness must use the approved WorkerPool in these values")
    pool = get("-n", agent_ns, "get", "workerpool", values.get("workerPool", "kagent-default"))
    if pool["spec"].get("sandboxClass") != "gvisor" or pool.get("status", {}).get("readyReplicas", 0) < 1:
        parser.error("Require a ready approved gVisor WorkerPool")
    workers = get("-n", agent_ns, "get", "pods", "-l", "ate.dev/worker-pool=" + pool["metadata"]["name"])
    if any(c["name"] == "istio-proxy" for p in workers["items"] for c in p["spec"]["containers"]):
        parser.error("Injected Substrate workers are outside this bundle's tested ingress-only mesh contract")
    ingress = values.get("ingress", {})
    mode = ingress.get("mode", "none")
    if mode not in {"local", "istio"}:
        parser.error("Select an HTTPS local or Istio ingress profile")
    tls_ns = ingress.get("istio", {}).get("namespace", "aks-istio-ingress") if mode == "istio" else args.namespace
    if mode in {"local", "istio"}:
        secret = get("-n", tls_ns, "get", "secret", ingress.get("tlsSecret", "flow-demo-tls"))
        if secret.get("type") != "kubernetes.io/tls" or not {"tls.crt", "tls.key"} <= secret.get("data", {}).keys():
            parser.error("Require an existing Kubernetes TLS Secret in the gateway namespace")
    if mode == "istio":
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", values.get("image", {}).get("digest", "")):
            parser.error("Pin the reviewed dashboard image digest for the work deployment")
        get("get", "crd", "gateways.networking.istio.io")
        selector = ingress.get("istio", {}).get("selector", "aks-istio-ingressgateway-internal")
        pods = get("-n", tls_ns, "get", "pods", "-l", "istio=" + selector)
        if not pods["items"]:
            parser.error("The selected managed Istio ingress gateway is absent")
    if mode == "istio" and ingress.get("istio", {}).get("existingGateway"):
        gateway_namespace, gateway_name = ingress["istio"]["existingGateway"].split("/", 1)
        if gateway_namespace != tls_ns:
            parser.error("existingGateway must be in the configured gateway namespace")
        get("-n", gateway_namespace, "get", "gateway.networking.istio.io", gateway_name)
    if not existing and values.get("model", {}).get("mode") == "live":
        live = values["model"]["live"]
        secret = get("-n", args.namespace, "get", "secret", live["existingSecret"])
        if live.get("secretKey", "api-key") not in secret.get("data", {}):
            parser.error("The configured existing model credential key is absent")
    releases = json.loads(subprocess.run(["helm", "--kube-context", args.context, "list", "-A", "-o", "json"], check=True, text=True, capture_output=True).stdout)
    for name, namespace, version in [("kagent", agent_ns, "1.0.0-alpha8"), ("substrate", "ate-system", "0.4.0-alpha1")]:
        if not any(r["name"] == name and r["namespace"] == namespace and r["chart"] == name + "-" + version for r in releases):
            parser.error("Installed platform chart versions must match the pinned bundle before deployment")
    forbidden = ("host.docker.internal", "127.0.0.1:18083", "18082", "EndpointSlice")
    if any(item in rendered for item in forbidden):
        parser.error("Rendered workload contains a host bridge or loopback runtime dependency")
    print(json.dumps({"context": args.context, "resources": len(resources), "ingress": mode,
                      "platform": "version-matched", "workerPool": "ready", "hostBridgeReferences": 0}))


if __name__ == "__main__":
    main()
