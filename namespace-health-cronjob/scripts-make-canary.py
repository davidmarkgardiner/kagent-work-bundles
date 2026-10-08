"""Render a manual canary Job from a rendered source manifest.

The canary topic and namespace come from the source manifest. A non-hourly
minute keeps its receipt slot separate from CronJob-owned hourly slots.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


def make_canary(source_path: Path, mode: str, slot: str | None = None) -> dict:
    if mode not in {"report-only", "publish"}:
        raise ValueError("mode must be report-only or publish")
    source = [item for item in yaml.safe_load_all(source_path.read_text()) if item]
    cron = next(item for item in source if item.get("kind") == "CronJob" and item["metadata"]["name"] == "namespace-health-assessor")
    config = next(item for item in source if item.get("kind") == "ConfigMap" and item["metadata"]["name"] == "namespace-health-policy")
    policy = json.loads(config["data"]["policy.json"])
    now = datetime.now(timezone.utc)
    if slot is None:
        at = now.replace(second=0, microsecond=0)
        if at.minute == 0:
            at -= timedelta(minutes=1)
    else:
        at = datetime.fromisoformat(slot.replace("Z", "+00:00"))
    if at.tzinfo is None or at.utcoffset() != timedelta(0) or at.minute == 0 or at.second or at.microsecond:
        raise ValueError("canary slot must be a non-hourly UTC minute")
    if at < now - timedelta(hours=2) or at > now + timedelta(minutes=5):
        raise ValueError("canary slot must be within the receiver admission window")
    slot_value = at.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    spec = deepcopy(cron["spec"]["jobTemplate"]["spec"])
    container = spec["template"]["spec"]["containers"][0]
    env = {item["name"]: item for item in container["env"]}
    for name, value in {
        "RUN_MODE": "manual-canary",
        "ALLOW_MANUAL_CANARY": "true",
        "CANARY_SLOT": slot_value,
        "KAFKA_TOPIC": policy["canary_topic"],
        "REPORT_ONLY": "true" if mode == "report-only" else "false",
    }.items():
        env[name] = {"name": name, "value": value}
    container["env"] = list(env.values())
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "generateName": "namespace-health-canary-",
            "namespace": cron["metadata"]["namespace"],
            "labels": cron["metadata"].get("labels", {}),
        },
        "spec": spec,
    }


if __name__ == "__main__":
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: scripts-make-canary.py RENDERED_SOURCE_YAML report-only|publish [UTC_NON_HOURLY_SLOT]")
    print(yaml.safe_dump(make_canary(Path(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None), sort_keys=False))
