#!/usr/bin/env python3
"""Retain the pinned Substrate egress telemetry delta in Helm delivery."""
import argparse
import hashlib
import sys
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    args = parser.parse_args()
    documents = [document for document in yaml.safe_load_all(sys.stdin) if document is not None]
    config = next((d for d in documents if d and d.get("kind") == "ConfigMap"
                   and d["metadata"]["name"] == "atenet-egress-agentgateway-config"), None)
    deployment = next((d for d in documents if d and d.get("kind") == "Deployment"
                       and d["metadata"]["name"] == "atenet-egress"), None)
    if config is None or deployment is None:
        parser.error("Expected the reviewed Substrate egress ConfigMap and Deployment")
    native = yaml.safe_load(config["data"]["config.yaml"])
    frontend = native["frontendPolicies"]
    frontend["tracing"] = {"host": args.endpoint.removeprefix("http://"), "protocol": "grpc", "randomSampling": 1}
    frontend.setdefault("accessLog", {})["otlp"] = {"host": args.endpoint.removeprefix("http://"), "protocol": "grpc"}
    content = yaml.safe_dump(native, sort_keys=False)
    config["data"]["config.yaml"] = content
    annotations = deployment["spec"]["template"]["metadata"].setdefault("annotations", {})
    annotations["flow-demo/telemetry-config"] = hashlib.sha256(content.encode()).hexdigest()
    yaml.safe_dump_all(documents, sys.stdout, sort_keys=False)


if __name__ == "__main__":
    main()
