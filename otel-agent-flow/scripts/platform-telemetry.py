#!/usr/bin/env python3
"""Configure telemetry on the explicitly selected, version-matched lab platform."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import yaml


def run(args, payload=None):
    return subprocess.run(args, input=payload, text=True, check=True, capture_output=True).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="agent-flow-demo")
    parser.add_argument("--agent-namespace", default="kagent")
    parser.add_argument("--substrate-namespace", default="ate-system")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--substrate-chart", default="oci://ghcr.io/kagent-dev/substrate/helm/substrate")
    parser.add_argument("--kagent-chart", default="oci://ghcr.io/kagent-dev/kagent/helm/kagent")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parents[1]
    state = args.state_dir.resolve()
    if state == bundle or bundle in state.parents:
        parser.error("State directory must be outside the public bundle")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    kubectl = ["kubectl", "--context", args.context]
    target = {"context": args.context, "namespace": args.namespace, "agentNamespace": args.agent_namespace,
              "substrateNamespace": args.substrate_namespace}
    target_file = state / "target.json"
    if target_file.exists() and json.loads(target_file.read_text()) != target:
        raise SystemExit("Private state directory belongs to a different target")
    if args.restore and not target_file.exists():
        raise SystemExit("No matching saved target exists for restoration")
    if not target_file.exists():
        target_file.write_text(json.dumps(target))
    releases = json.loads(run(["helm", "--kube-context", args.context, "list", "-A", "-o", "json"]))
    versions = [("substrate", args.substrate_namespace, "0.4.0-alpha1"),
                ("kagent", args.agent_namespace, "1.0.0-alpha8")]
    for name, namespace, version in versions:
        release = next((r for r in releases if r["name"] == name and r["namespace"] == namespace), None)
        if not release or release["chart"] != name + "-" + version:
            raise SystemExit(f"Expected installed {name} chart {version} in {namespace}; no platform upgrade is performed")
    endpoint = f"http://flow-collector.{args.namespace}.svc.cluster.local:4317"
    changes = {
        "substrate": {"otel": {"endpoint": endpoint, "traces": {"samplingRatio": 1}}},
        "kagent": {"otel": {"exporter": {"otlp": {"endpoint": endpoint}}, "traces": {"enabled": True},
                              "logs": {"enabled": True}, "capture": {"messageContent": False, "rawApiBodies": False}}},
    }
    config = json.loads(run(kubectl + ["-n", args.substrate_namespace, "get", "configmap", "atenet-egress-agentgateway-config", "-o", "json"]))
    backup = state / "egress-original.json"
    if not backup.exists():
        if args.restore:
            raise SystemExit("Original egress configuration is missing")
        backup.write_text(json.dumps(config))
        backup.chmod(0o600)
    base_egress = yaml.safe_load(config["data"]["config.yaml"])
    for name, namespace, version in versions:
        original = run(["helm", "--kube-context", args.context, "get", "values", name, "-n", namespace, "-o", "json"])
        backup = state / (name + "-original-values.json")
        if not backup.exists():
            if args.restore:
                raise SystemExit(f"Original {name} values are missing")
            backup.write_text(original)
            backup.chmod(0o600)
        values = state / (name + "-telemetry.json")
        restore_flags = ["--reuse-values"]
        change = changes[name]
        if args.restore:
            current = json.loads(original)
            saved = json.loads(backup.read_text())
            current_otel = current.get("otel", {})
            current_endpoint = current_otel.get("endpoint") if name == "substrate" else current_otel.get("exporter", {}).get("otlp", {}).get("endpoint")
            if current_endpoint != endpoint:
                raise SystemExit(f"{name} telemetry was changed by another owner; review before restoring")
            if "otel" in saved:
                current["otel"] = saved["otel"]
            else:
                current.pop("otel", None)
            change, restore_flags = current, ["--reset-values"]
        values.write_text(json.dumps(change))
        values.chmod(0o600)
        chart = args.substrate_chart if name == "substrate" else args.kagent_chart
        metadata = yaml.safe_load(run(["helm", "show", "chart", chart, "--version", version]))
        if metadata["version"] != version:
            raise SystemExit(f"Supplied {name} archive does not match {version}")
        post_renderer = []
        if name == "substrate" and not args.restore:
            post_renderer = ["--post-renderer", sys.executable,
                             "--post-renderer-args", str(bundle / "scripts/substrate-post-render.py"),
                             "--post-renderer-args=--endpoint", "--post-renderer-args=" + endpoint]
        run(["helm", "--kube-context", args.context, "upgrade", name, chart,
             "--version", version, "-n", namespace, *restore_flags, "-f", str(values), *post_renderer])
        print(f"Configured {name} telemetry on {args.context}", flush=True)
    config = json.loads(run(kubectl + ["-n", args.substrate_namespace, "get", "configmap", "atenet-egress-agentgateway-config", "-o", "json"]))
    document = base_egress
    frontend = document["frontendPolicies"]
    if args.restore:
        saved_config = json.loads((state / "egress-original.json").read_text())
        saved_frontend = yaml.safe_load(saved_config["data"]["config.yaml"])["frontendPolicies"]
        if "tracing" in saved_frontend:
            frontend["tracing"] = saved_frontend["tracing"]
        else:
            frontend.pop("tracing", None)
        access = frontend.setdefault("accessLog", {})
        if "otlp" in saved_frontend.get("accessLog", {}):
            access["otlp"] = saved_frontend["accessLog"]["otlp"]
        else:
            access.pop("otlp", None)
    else:
        frontend["tracing"] = {"host": endpoint.removeprefix("http://"), "protocol": "grpc", "randomSampling": 1}
        frontend.setdefault("accessLog", {})["otlp"] = {"host": endpoint.removeprefix("http://"), "protocol": "grpc"}
    content = yaml.safe_dump(document, sort_keys=False)
    config["data"]["config.yaml"] = content
    config["metadata"].pop("managedFields", None)
    payload = json.dumps(config)
    run(kubectl + ["apply", "--dry-run=server", "-f", "-"], payload)
    run(kubectl + ["apply", "-f", "-"], payload)
    patch = {"spec": {"template": {"metadata": {"annotations": {
        "flow-demo/telemetry-config": hashlib.sha256(content.encode()).hexdigest()}}}}}
    run(kubectl + ["-n", args.substrate_namespace, "patch", "deployment", "atenet-egress", "--type=merge", "-p", json.dumps(patch)])
    run(kubectl + ["-n", args.substrate_namespace, "rollout", "status", "deployment/atenet-egress", "--timeout=120s"])
    for resource in ["deployment/ate-api-server", "deployment/ate-controller", "deployment/atenet-router", "daemonset/atelet"]:
        run(kubectl + ["-n", args.substrate_namespace, "rollout", "status", resource, "--timeout=180s"])
    run(kubectl + ["-n", args.agent_namespace, "rollout", "status", "deployment/kagent-controller", "--timeout=180s"])
    print("Native egress tracing configured. Private rollback values saved outside the bundle.")


if __name__ == "__main__":
    main()
