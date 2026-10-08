"""Render the two-namespace workplace pilot into a private directory.

The input JSON contains approved names and references, never secret values.
Keep both the input and output outside this public repository.
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
PUBLIC_REPO = ROOT.parents[1]
TEMPLATES = ROOT / "manifests" / "workplace"
TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
DNS_NAME = re.compile(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?")


def outside_repo(path: Path) -> None:
    if path.resolve().is_relative_to(PUBLIC_REPO):
        raise ValueError("private configuration and rendered manifests must stay outside the public bundle")


def fill(text: str, values: dict[str, str]) -> str:
    missing = set(TOKEN.findall(text)) - values.keys()
    if missing:
        raise ValueError("missing template values: " + ", ".join(sorted(missing)))
    return TOKEN.sub(lambda match: values[match.group(1)], text)


def main(config_path: Path, output_dir: Path) -> None:
    outside_repo(config_path)
    outside_repo(output_dir)
    values = json.loads(config_path.read_text())
    if not isinstance(values, dict) or any(
        not isinstance(value, str) or not value or "{{" in value or "}}" in value
        for value in values.values()
    ):
        raise ValueError("every supplied value must be a nonempty plain string")
    for key in ("ASSESSOR_NAMESPACE", "RECEIVER_NAMESPACE", "WATCHED_NAMESPACE_1", "WATCHED_NAMESPACE_2"):
        if not DNS_NAME.fullmatch(values.get(key, "")) or len(values[key]) > 63:
            raise ValueError(f"invalid Kubernetes namespace: {key}")
    if values["WATCHED_NAMESPACE_1"] == values["WATCHED_NAMESPACE_2"]:
        raise ValueError("pilot namespaces must be distinct")
    if not re.fullmatch(r".+@sha256:[0-9a-f]{64}", values.get("APPROVED_IMAGE_REF", "")):
        raise ValueError("APPROVED_IMAGE_REF must be an immutable image digest")
    if values.get("SCHEDULED_TOPIC") == values.get("CANARY_TOPIC"):
        raise ValueError("canary and scheduled Kafka topics must be distinct")

    policy_text = fill((TEMPLATES / "pilot-two-namespaces.policy.template.json").read_text(), values)
    policy = json.loads(policy_text)
    if len(policy["watched_namespaces"]) != 2 or any(
        not entries for entries in policy["application_containers"].values()
    ):
        raise ValueError("two watched namespaces need explicit application containers")
    rendered_values = {**values, "POLICY_JSON": json.dumps(policy, sort_keys=True, separators=(",", ":"))}
    source_text = fill((TEMPLATES / "pilot-two-namespaces.source.template.yaml").read_text(), rendered_values)
    receiver_text = fill((TEMPLATES / "receiver.template.yaml").read_text(), rendered_values)
    source = [item for item in yaml.safe_load_all(source_text) if item]
    receiver = [item for item in yaml.safe_load_all(receiver_text) if item]
    if len(source) != 11 or len(receiver) != 13:
        raise ValueError("unexpected source or receiver object count")
    canary_event_source = deepcopy(next(item for item in receiver if item["kind"] == "EventSource"))
    canary_event_source["metadata"]["name"] = "namespace-health-canary-kafka"
    canary_event_source["spec"]["kafka"]["reports"]["topic"] = values["CANARY_TOPIC"]
    canary_event_source["spec"]["kafka"]["reports"]["consumerGroup"]["groupName"] = values["RECEIVER_GROUP"] + "-canary"
    canary_sensor = deepcopy(next(item for item in receiver if item["kind"] == "Sensor"))
    canary_sensor["metadata"]["name"] = "namespace-health-canary-receipt"
    canary_sensor["spec"]["dependencies"][0]["eventSourceName"] = canary_event_source["metadata"]["name"]
    canary_sensor["spec"]["triggers"][0]["template"]["k8s"]["source"]["resource"]["metadata"]["generateName"] = "namespace-health-canary-receipt-"
    canary_receiver = [canary_event_source, canary_sensor]
    cron = next(item for item in source if item["kind"] == "CronJob")
    if cron["spec"]["schedule"] != "0 * * * *" or cron["spec"]["suspend"] is not True:
        raise ValueError("pilot source must start as a suspended hourly CronJob")
    allowed = {"kube-system", *policy["watched_namespaces"]}
    role = next(item for item in source if item["kind"] == "ClusterRole")
    if set(role["rules"][0]["resourceNames"]) != allowed:
        raise ValueError("namespace identity RBAC exceeds pilot scope")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "source.yaml").write_text(yaml.safe_dump_all(source, sort_keys=False, explicit_start=True))
    (output_dir / "receiver.yaml").write_text(yaml.safe_dump_all(receiver, sort_keys=False, explicit_start=True))
    (output_dir / "canary-receiver.yaml").write_text(yaml.safe_dump_all(canary_receiver, sort_keys=False, explicit_start=True))
    print(f"rendered {len(source)} source, {len(receiver)} scheduled receiver and {len(canary_receiver)} canary receiver objects in {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: scripts-render-workplace-pilot.py PRIVATE_CONFIG_JSON EMPTY_PRIVATE_OUTPUT_DIR")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
