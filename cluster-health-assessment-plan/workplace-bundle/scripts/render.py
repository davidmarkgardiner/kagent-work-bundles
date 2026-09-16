#!/usr/bin/env python3
"""Render placeholder-free worker and manager manifests from reviewed values."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
IMAGE = re.compile(r"^[a-zA-Z0-9._:/-]+@sha256:[0-9a-f]{64}$")
DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


REQUIRED = {
    "AKS_MCP_SERVER_NAME", "ASSESSOR_IMAGE", "CLUSTER_HEALTH_ALERT_TOPIC",
    "CLUSTER_HEALTH_CONSUMER_GROUP", "CLUSTER_ID", "CRITICAL_NAMESPACES",
    "FOX_IMAGE", "GITLAB_API_URL", "GITLAB_CREDENTIALS_SECRET",
    "GITLAB_EGRESS_CIDR", "GITLAB_PORT", "GITLAB_PROJECT_ID",
    "GITLAB_WRITE_ENABLED", "KAFKA_BOOTSTRAP", "KAFKA_CREDENTIALS_SECRET",
    "KAFKA_EGRESS_CIDR", "KAGENT_A2A_PORT", "KAGENT_A2A_URL",
    "KAGENT_MODEL_CONFIG", "KAGENT_NAMESPACE", "KAFKA_PORT",
    "KUBERNETES_API_CIDR", "MANAGER_KUBERNETES_API_CIDR", "MCP_CLUSTER_TARGET",
    "PROMETHEUS_NAMESPACE", "EXPECTED_NAMESPACE_COUNT", "SOURCE_GENERATION",
    "TOOLBOX_IMAGE", "VECTOR_IMAGE",
}


def validate(values: dict) -> None:
    missing = sorted(REQUIRED - values.keys())
    extra = sorted(values.keys() - REQUIRED)
    if missing or extra:
        raise ValueError("values keys differ: missing={} extra={}".format(missing, extra))
    if any(not isinstance(value, str) or not value.strip() for value in values.values()):
        raise ValueError("every value must be a non-empty string")
    if any(TOKEN.search(value) for value in values.values()):
        raise ValueError("values file still contains placeholder tokens")
    for name in ("ASSESSOR_IMAGE", "FOX_IMAGE", "TOOLBOX_IMAGE", "VECTOR_IMAGE"):
        if not IMAGE.fullmatch(values[name]):
            raise ValueError("{} must be an immutable image@sha256 reference".format(name))
    for name in ("GITLAB_EGRESS_CIDR", "KAFKA_EGRESS_CIDR", "KUBERNETES_API_CIDR", "MANAGER_KUBERNETES_API_CIDR"):
        ipaddress.ip_network(values[name], strict=False)
    for name in ("AKS_MCP_SERVER_NAME", "GITLAB_CREDENTIALS_SECRET", "KAFKA_CREDENTIALS_SECRET", "PROMETHEUS_NAMESPACE", "KAGENT_NAMESPACE"):
        if not DNS_LABEL.fullmatch(values[name]):
            raise ValueError("{} must be a Kubernetes DNS label".format(name))
    if not values["KAGENT_A2A_URL"].endswith("/"):
        raise ValueError("KAGENT_A2A_URL must include the required trailing slash")
    for name, lower, upper in (("GITLAB_PORT", 1, 65535), ("KAFKA_PORT", 1, 65535), ("KAGENT_A2A_PORT", 1, 65535), ("EXPECTED_NAMESPACE_COUNT", 1, 1000)):
        if not values[name].isdigit() or not lower <= int(values[name]) <= upper:
            raise ValueError("{} must be an integer from {} to {}".format(name, lower, upper))
    scope = json.loads((ROOT.parent / "fox-mesh/namespaces.json").read_text(encoding="utf-8"))
    actual_count = len(scope.get("namespaces", []))
    if int(values["EXPECTED_NAMESPACE_COUNT"]) != actual_count:
        raise ValueError(
            "EXPECTED_NAMESPACE_COUNT {} does not match namespaces.json count {}".format(
                values["EXPECTED_NAMESPACE_COUNT"], actual_count
            )
        )
    parsed_a2a = urllib.parse.urlparse(values["KAGENT_A2A_URL"])
    expected_suffix = ".{}.svc.cluster.local".format(values["KAGENT_NAMESPACE"])
    if parsed_a2a.scheme not in {"http", "https"} or not parsed_a2a.hostname:
        raise ValueError("KAGENT_A2A_URL must be an HTTP(S) service URL")
    if not parsed_a2a.hostname.endswith(expected_suffix):
        raise ValueError("KAGENT_A2A_URL must target the configured KAGENT_NAMESPACE")
    if parsed_a2a.port != int(values["KAGENT_A2A_PORT"]):
        raise ValueError("KAGENT_A2A_URL port must match KAGENT_A2A_PORT")
    brokers = [item.strip() for item in values["KAFKA_BOOTSTRAP"].split(",")]
    if not brokers or any(not re.fullmatch(r"[A-Za-z0-9.-]+:[0-9]+", item) for item in brokers):
        raise ValueError("KAFKA_BOOTSTRAP must be a comma-separated host:port list")
    if any(int(item.rsplit(":", 1)[1]) != int(values["KAFKA_PORT"]) for item in brokers):
        raise ValueError("every KAFKA_BOOTSTRAP broker must use KAFKA_PORT")
    gitlab = urllib.parse.urlparse(values["GITLAB_API_URL"])
    if gitlab.scheme != "https" or not gitlab.hostname or gitlab.path not in {"", "/"}:
        raise ValueError("GITLAB_API_URL must be an HTTPS origin without a path")
    if (gitlab.port or 443) != int(values["GITLAB_PORT"]):
        raise ValueError("GITLAB_API_URL port must match GITLAB_PORT")
    if values["GITLAB_WRITE_ENABLED"] not in {"true", "false"}:
        raise ValueError("GITLAB_WRITE_ENABLED must be true or false")
    if ":latest" in " ".join(values.values()):
        raise ValueError("floating latest tags are forbidden")


def render(component: str, values: dict) -> str:
    generated = subprocess.run(
        ["kubectl", "kustomize", str(ROOT / component)],
        check=True, text=True, capture_output=True,
    ).stdout
    for name in ("ASSESSOR_IMAGE", "FOX_IMAGE", "VECTOR_IMAGE"):
        generated = generated.replace("{{{{{}}}}}:workplace".format(name), values[name])
    generated = re.sub(
        r"(^\s*(?:-\s*)?port:\s*)9092(\s*$)",
        lambda match: match.group(1) + values["KAFKA_PORT"] + match.group(2),
        generated,
        flags=re.MULTILINE,
    )
    generated = re.sub(
        r"(^\s*(?:-\s*)?port:\s*)8083(\s*$)",
        lambda match: match.group(1) + values["KAGENT_A2A_PORT"] + match.group(2),
        generated,
        flags=re.MULTILINE,
    )
    generated = re.sub(
        r"(^\s*(?:-\s*)?port:\s*)31443(\s*$)",
        lambda match: match.group(1) + values["GITLAB_PORT"] + match.group(2),
        generated,
        flags=re.MULTILINE,
    )
    for name, value in values.items():
        generated = generated.replace("{{{{{}}}}}".format(name), value)
    unresolved = sorted(set(TOKEN.findall(generated)))
    if unresolved:
        raise ValueError("unresolved placeholders in {}: {}".format(component, unresolved))
    if ":latest" in generated:
        raise ValueError("rendered manifest contains a floating latest tag")
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--values", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    values = json.loads(args.values.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("values file must contain one JSON object")
    validate(values)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for component in ("worker", "manager"):
        target = args.output_dir / (component + ".yaml")
        target.write_text(render(component, values), encoding="utf-8")
        print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
