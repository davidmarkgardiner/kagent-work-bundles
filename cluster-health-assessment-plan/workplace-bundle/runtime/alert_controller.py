#!/usr/bin/env python3
"""Emit bounded cluster-health transitions for Vector to publish to Kafka.

The controller never talks to Kafka.  It reads the latest immutable B1
snapshot, emits at most one compact daily contract after the configured UTC
slot, appends that contract to a shared NDJSON file, and persists only its small
dedupe/episode state in a named ConfigMap. Vector owns Kafka TLS/SASL, delivery
retries, and broker telemetry.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount")
STATE_CONFIGMAP = "cluster-health-alert-state"
LATEST_CONFIGMAP = "cluster-health-latest"
SCHEMA_VERSION = "cluster-health.alert.v1"


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_json(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def event_hash(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


def validate_snapshot(snapshot: dict, *, cluster_id: str, generation: str,
                      max_age_seconds: int, now: datetime) -> None:
    if snapshot.get("cluster_id") != cluster_id:
        raise ValueError("snapshot cluster_id does not match controller binding")
    if snapshot.get("source_generation") != generation:
        raise ValueError("snapshot source_generation does not match controller binding")
    if not isinstance(snapshot.get("snapshot_seq"), int) or snapshot["snapshot_seq"] < 1:
        raise ValueError("snapshot_seq must be a positive integer")
    if not isinstance(snapshot.get("gate"), dict) or not isinstance(snapshot["gate"].get("active"), bool):
        raise ValueError("snapshot gate.active must be boolean")
    completed = parse_timestamp(snapshot.get("completed_at", ""))
    age = (now - completed).total_seconds()
    if age < -60 or age > max_age_seconds:
        raise ValueError("snapshot is outside the accepted freshness window")
    score = snapshot.get("display_score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("display_score must be an integer from 0 to 100")


def compact_domains(snapshot: dict) -> dict:
    result = {}
    for name, source in sorted((snapshot.get("domains") or {}).items()):
        if not isinstance(source, dict):
            continue
        result[name] = {
            "status": source.get("status", "unknown"),
            "reasons": [str(reason)[:160] for reason in (source.get("reasons") or [])[:3]],
        }
    return result


def compact_group(source: dict) -> dict | None:
    if not isinstance(source, dict):
        return None
    namespace = str(source.get("namespace", ""))[:63]
    owner = source.get("owner") or {}
    owner_kind = str(owner.get("kind", ""))[:63] if isinstance(owner, dict) else ""
    owner_name = str(owner.get("name", ""))[:253] if isinstance(owner, dict) else ""
    family = str(source.get("symptom_family", ""))[:63]
    if not namespace or not family:
        return None
    count = source.get("count", 0)
    if not isinstance(count, int) or count < 0:
        count = 0
    return {
        "namespace": namespace,
        "owner_kind": owner_kind,
        "owner_name": owner_name,
        "symptom_family": family,
        "count": count,
        "sources": sorted(str(item)[:32] for item in (source.get("source_counts") or {}).keys())[:4],
    }


def compact_groups(snapshot: dict, top_n: int) -> list[dict]:
    groups = [group for group in (compact_group(item) for item in snapshot.get("problem_groups", [])) if group]
    groups.sort(key=lambda item: (-item["count"], item["namespace"], item["owner_kind"], item["owner_name"], item["symptom_family"]))
    return groups[:top_n]


def severity(domains: dict) -> str:
    values = {item.get("status") for item in domains.values() if isinstance(item, dict)}
    if "critical" in values:
        return "critical"
    if "degraded" in values:
        return "degraded"
    if "watch" in values:
        return "watch"
    return "healthy"


def eligible_daily_slot(now: datetime, hour_utc: int, minute_utc: int) -> str | None:
    current = now.astimezone(timezone.utc)
    if (current.hour, current.minute) < (hour_utc, minute_utc):
        return None
    return current.date().isoformat()


def build_event(snapshot: dict, pointer: dict, previous: dict, *, now: datetime,
                daily_slot: str | None, top_n: int,
                cluster_ref: str) -> tuple[dict | None, dict]:
    gate = snapshot["gate"]
    active = gate["active"]
    was_active = bool(previous.get("active", False))
    now_text = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    episode_id = str(previous.get("episode_id", ""))
    if not daily_slot or previous.get("last_daily_slot") == daily_slot:
        new_state = dict(previous)
        new_state.update({
            "active": active,
            "last_seen_snapshot_seq": snapshot["snapshot_seq"],
            "last_seen_checksum": snapshot.get("checksum", ""),
        })
        return None, new_state

    if active and not was_active:
        episode_id = event_hash(snapshot["cluster_id"], snapshot["source_generation"], snapshot["snapshot_seq"])[:20]
    action = "investigate" if active else "healthy"

    new_state = dict(previous)
    new_state.update({
        "active": active,
        "episode_id": episode_id if active else "",
        "last_daily_slot": daily_slot,
        "last_seen_snapshot_seq": snapshot["snapshot_seq"],
        "last_seen_checksum": snapshot.get("checksum", ""),
    })

    groups = compact_groups(snapshot, top_n)
    namespaces = sorted({group["namespace"] for group in groups})
    event_id = "sha256:" + event_hash(
        snapshot["cluster_id"], snapshot["source_generation"], episode_id,
        action, daily_slot, snapshot["snapshot_seq"], snapshot.get("checksum", ""),
    )
    domains = compact_domains(snapshot)
    coverage = snapshot.get("coverage") or {}
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "dedupe_key": "cluster-health/{}/daily/{}".format(snapshot["cluster_id"], daily_slot),
        "action": action,
        "automation_allowed": False,
        "emitted_at": now_text,
        "dispatch": {
            "workflow_name": "cluster-health-investigation-" + event_id[-20:],
        },
        "cluster": {
            "id": snapshot["cluster_id"],
            "source_generation": snapshot["source_generation"],
            "mcp_target": cluster_ref,
        },
        "health": {
            "display_score": snapshot["display_score"],
            "severity": severity(domains),
            "gate_reason": str(gate.get("reason", ""))[:240],
            "coverage_complete": bool(coverage.get("complete", False)),
            "domains": domains,
        },
        "scope": {
            "namespaces": namespaces,
            "top_problem_groups": groups,
            "problem_group_total": int(snapshot.get("problem_group_total", len(groups)) or 0),
            "problem_groups_truncated": bool(snapshot.get("problem_groups_truncated", False)),
        },
        "evidence": {
            "daily_slot_utc": daily_slot,
            "snapshot_name": str(pointer.get("snapshot", ""))[:253],
            "snapshot_seq": snapshot["snapshot_seq"],
            "snapshot_checksum": str(snapshot.get("checksum", ""))[:80],
            "snapshot_completed_at": snapshot["completed_at"],
            "policy_version": str(snapshot.get("policy_version", ""))[:80],
        },
        "investigation": {
            "read_only": True,
            "requested_checks": [
                "Confirm current node and control-plane health",
                "Inspect current events in the supplied namespaces",
                "Inspect current workload status and bounded pod logs only where symptoms justify it",
                "Correlate repeated symptoms to stable workload or node root causes",
                "Return one evidence-backed cluster summary; do not create per-finding tickets",
            ],
        },
    }
    new_state.update({
        "last_action": action,
        "last_emitted_at": now_text,
        "last_event_id": event_id,
        "last_emitted_snapshot_seq": snapshot["snapshot_seq"],
    })
    return event, new_state


class KubernetesApi:
    def __init__(self, namespace: str):
        host = os.environ["KUBERNETES_SERVICE_HOST"]
        port = os.environ["KUBERNETES_SERVICE_PORT"]
        self.base = "https://{}:{}".format(host, port)
        self.namespace = namespace
        self.token = (SA_PATH / "token").read_text(encoding="utf-8").strip()
        self.context = ssl.create_default_context(cafile=str(SA_PATH / "ca.crt"))

    def request(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        data = canonical_json(body) if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Authorization", "Bearer " + self.token)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=15, context=self.context) as response:
            return json.loads(response.read().decode())

    def configmap(self, name: str) -> dict:
        path = "/api/v1/namespaces/{}/configmaps/{}".format(self.namespace, name)
        return self.request(path)

    def optional_configmap(self, name: str) -> dict:
        try:
            return self.configmap(name)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            raise

    def save_state(self, document: dict, current: dict) -> None:
        metadata = {
            "name": STATE_CONFIGMAP,
            "namespace": self.namespace,
            "labels": {
                "app.kubernetes.io/name": "cluster-health-alert-bridge",
                "app.kubernetes.io/component": "dispatch-state",
            },
        }
        body = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": metadata,
            "data": {"state.json": canonical_json(document).decode()},
        }
        base = "/api/v1/namespaces/{}/configmaps".format(self.namespace)
        if current:
            body["metadata"]["resourceVersion"] = (current.get("metadata") or {}).get("resourceVersion")
            self.request(base + "/" + STATE_CONFIGMAP, method="PUT", body=body)
        else:
            self.request(base, method="POST", body=body)


def load_document(configmap: dict, key: str) -> dict:
    value = (configmap.get("data") or {}).get(key)
    if not value:
        return {}
    document = json.loads(value)
    if not isinstance(document, dict):
        raise ValueError("{} must contain a JSON object".format(key))
    return document


def append_event(path: Path, event: dict, max_event_bytes: int) -> int:
    encoded = canonical_json(event) + b"\n"
    if len(encoded) > max_event_bytes:
        raise ValueError("alert event exceeds configured byte limit")
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
    try:
        written = os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if written != len(encoded):
        raise OSError("short write while appending alert event")
    return written


def touch(path: Path) -> None:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    path.write_text(str(int(time.time())), encoding="utf-8")


def run_once(api: KubernetesApi, *, cluster_id: str, generation: str,
             cluster_ref: str, output: Path, top_n: int,
             max_event_bytes: int, max_snapshot_age_seconds: int,
             daily_hour_utc: int, daily_minute_utc: int) -> dict:
    now = datetime.now(timezone.utc)
    pointer = load_document(api.configmap(LATEST_CONFIGMAP), "pointer.json")
    snapshot_name = pointer.get("snapshot")
    if not snapshot_name:
        raise ValueError("latest pointer does not name a snapshot")
    snapshot = load_document(api.configmap(snapshot_name), "snapshot.json")
    validate_snapshot(snapshot, cluster_id=cluster_id, generation=generation,
                      max_age_seconds=max_snapshot_age_seconds, now=now)
    if pointer.get("checksum") != snapshot.get("checksum"):
        raise ValueError("latest pointer checksum does not match snapshot")
    state_cm = api.optional_configmap(STATE_CONFIGMAP)
    previous = load_document(state_cm, "state.json") if state_cm else {}
    event, state = build_event(
        snapshot, pointer, previous, now=now,
        daily_slot=eligible_daily_slot(now, daily_hour_utc, daily_minute_utc),
        top_n=top_n, cluster_ref=cluster_ref,
    )
    emitted = False
    if event:
        append_event(output, event, max_event_bytes)
        emitted = True
    api.save_state(state, state_cm)
    return {
        "snapshot_seq": snapshot["snapshot_seq"],
        "gate_active": snapshot["gate"]["active"],
        "emitted": emitted,
        "action": event.get("action") if event else None,
        "event_id": event.get("event_id") if event else None,
    }


def positive_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError("{} must be between {} and {}".format(name, minimum, maximum))
    return value


def main() -> int:
    namespace = os.environ.get("STATE_NAMESPACE", "cluster-health-system")
    cluster_id = os.environ["CLUSTER_ID"]
    generation = os.environ["SOURCE_GENERATION"]
    cluster_ref = os.environ["MCP_CLUSTER_TARGET"]
    output = Path(os.environ.get("ALERT_OUTPUT_PATH", "/var/run/cluster-health/alerts.ndjson"))
    live_path = Path(os.environ.get("LIVENESS_FILE", "/var/run/cluster-health/controller.live"))
    ready_path = Path(os.environ.get("READINESS_FILE", "/var/run/cluster-health/controller.ready"))
    poll_seconds = positive_int("ALERT_POLL_SECONDS", 30, minimum=10, maximum=300)
    daily_hour_utc = positive_int("DAILY_REPORT_HOUR_UTC", 7, minimum=0, maximum=23)
    daily_minute_utc = positive_int("DAILY_REPORT_MINUTE_UTC", 30, minimum=0, maximum=59)
    top_n = positive_int("ALERT_TOP_N", 10, minimum=1, maximum=20)
    max_event_bytes = positive_int("ALERT_MAX_EVENT_BYTES", 65536, minimum=4096, maximum=131072)
    max_snapshot_age = positive_int("MAX_SNAPSHOT_AGE_SECONDS", 900, minimum=300, maximum=3600)
    api = KubernetesApi(namespace)
    while True:
        try:
            result = run_once(
                api, cluster_id=cluster_id, generation=generation,
                cluster_ref=cluster_ref, output=output,
                top_n=top_n,
                max_event_bytes=max_event_bytes,
                max_snapshot_age_seconds=max_snapshot_age,
                daily_hour_utc=daily_hour_utc,
                daily_minute_utc=daily_minute_utc,
            )
            print(json.dumps(result, sort_keys=True), flush=True)
            touch(ready_path)
        except Exception as exc:  # keep the bridge alive; readiness is Vector/Kafka plus fresh snapshots
            print(json.dumps({"error": type(exc).__name__, "message": str(exc)[:240]}), file=sys.stderr, flush=True)
        touch(live_path)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
