#!/usr/bin/env python3
"""B1 report-only Kubernetes cluster health collector.

This program talks only to the Kubernetes API. It contains no Kafka, model,
webhook, GitHub, or GitLab client.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import resource
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from health import (
    DOMAIN_ORDER,
    canonical_checksum,
    counter_delta,
    display_score,
    evaluate_gate,
    event_timestamp,
    is_successful_job_pod,
    parse_k8s_timestamp,
    problem_key,
    recent_termination,
    stable_owner,
)

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
STATE_NAMESPACE = os.environ.get("STATE_NAMESPACE", "cluster-health-system")
POINTER_NAME = "cluster-health-latest"
SNAPSHOT_PREFIX = "cluster-health-snapshot-"
REPORT_PREFIX = "cluster-health-report-"
POLICY_VERSION = "b1-policy-v3-fox-shadow"
BASELINE_VERSION = "b1-absolute-v1"
SCHEMA_VERSION = 1
ALLOWED_WARNING_REASONS_VERSION = "k8s-warning-v1"
ALLOWED_WARNING_REASONS = {
    "BackOff", "Evicted", "Failed", "FailedAttachVolume", "FailedCreate",
    "FailedCreatePodSandBox", "FailedMount", "FailedScheduling", "OOMKilling",
    "Preempted", "Unhealthy", "VolumeResizeFailed",
}
STATUS_RANK = {"healthy": 0, "watch": 1, "degraded": 2, "critical": 3}
ERROR_LINE = re.compile(r"\b(error|exception|fatal|panic|traceback|oomkilled)\b", re.I)
NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def strict_bool(name: str, required: bool = True) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        if required:
            raise ValueError("{} must be set explicitly".format(name))
        return None
    if raw not in ("true", "false"):
        raise ValueError("{} must be exactly true or false".format(name))
    return raw == "true"


def bounded_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError("{} must be an integer".format(name)) from exc
    if not low <= value <= high:
        raise ValueError("{} must be between {} and {}".format(name, low, high))
    return value


def load_config() -> dict:
    downstream = strict_bool("DOWNSTREAM_TRIAGE_ENABLED")
    resource_specs = strict_bool("CHECK_RESOURCE_SPECS_ENABLED")
    if downstream:
        raise ValueError("B1 requires DOWNSTREAM_TRIAGE_ENABLED=false")
    if resource_specs:
        raise ValueError("B1 requires CHECK_RESOURCE_SPECS_ENABLED=false")
    namespaces = [x.strip() for x in os.environ.get("WATCH_NAMESPACES", "").split(",") if x.strip()]
    if not namespaces or any(not NAME_RE.match(ns) for ns in namespaces):
        raise ValueError("WATCH_NAMESPACES must contain explicit Kubernetes namespace names")
    critical = {x.strip() for x in os.environ.get("CRITICAL_NAMESPACES", "kube-system").split(",") if x.strip()}
    if not critical.issubset(set(namespaces)):
        raise ValueError("CRITICAL_NAMESPACES must be a subset of WATCH_NAMESPACES")
    placement_coverage = os.environ.get("POD_PLACEMENT_COVERAGE", "").strip()
    if placement_coverage not in ("full", "partial"):
        raise ValueError("POD_PLACEMENT_COVERAGE must be exactly full or partial")
    fox_mode = os.environ.get("FOX_MESH_MODE", "disabled").strip()
    if fox_mode not in ("disabled", "shadow"):
        raise ValueError("FOX_MESH_MODE must be disabled or shadow; ConfigMap evidence is never authoritative")
    fox_state_configmap = os.environ.get("FOX_STATE_CONFIGMAP_NAME", "fox-autonomous-monitor-state").strip()
    if fox_mode != "disabled" and not NAME_RE.match(fox_state_configmap):
        raise ValueError("FOX_STATE_CONFIGMAP_NAME must be a Kubernetes name")
    return {
        "cluster": os.environ.get("CLUSTER_ID", "").strip(),
        "generation": os.environ.get("SOURCE_GENERATION", "").strip(),
        "namespaces": namespaces,
        "critical_namespaces": critical,
        "pod_placement_coverage": placement_coverage,
        "event_window_minutes": bounded_int("EVENT_WINDOW_MINUTES", 15, 1, 1440),
        "log_window_seconds": bounded_int("LOG_WINDOW_SECONDS", 300, 60, 3600),
        "max_log_pods": bounded_int("MAX_LOG_PODS", 20, 0, 50),
        "top_n": bounded_int("TOP_N", 20, 1, 100),
        "max_bytes": bounded_int("SNAPSHOT_MAX_BYTES", 256 * 1024, 32 * 1024, 256 * 1024),
        "retain": bounded_int("SNAPSHOT_RETAIN", 288, 2, 2016),
        "max_state_observations": bounded_int("MAX_STATE_OBSERVATIONS", 2000, 100, 5000),
        "fox_mesh_mode": fox_mode,
        "fox_state_configmap": fox_state_configmap,
    }


class Api:
    def __init__(self):
        host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
        port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
        self.base = "https://{}:{}".format(host, port)
        self.ctx = ssl.create_default_context(cafile=os.path.join(SA_DIR, "ca.crt"))
        with open(os.path.join(SA_DIR, "token"), encoding="utf-8") as fh:
            self.token = fh.read().strip()
        self.calls = 0
        self.response_bytes = 0
        self.duration_ms = 0.0
        self.calls_by_scope = Counter()
        self.bytes_by_scope = Counter()

    def request(self, path: str, method: str = "GET", body: dict | None = None, raw: bool = False):
        started = time.monotonic()
        data = json.dumps(body, separators=(",", ":")).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Accept", "*/*" if raw else "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30, context=self.ctx) as response:
                payload = response.read()
        finally:
            self.calls += 1
            self.duration_ms += (time.monotonic() - started) * 1000
        self.response_bytes += len(payload)
        match = re.search(r"/namespaces/([^/]+)", path)
        scope = urllib.parse.unquote(match.group(1)) if match else "cluster"
        self.calls_by_scope[scope] += 1
        self.bytes_by_scope[scope] += len(payload)
        if raw:
            return payload.decode(errors="replace")
        return json.loads(payload) if payload else {}

    def list_items(self, path: str) -> list:
        """Follow Kubernetes list pagination; partial lists are never complete."""
        items = []
        cursor = ""
        for _ in range(50):
            request_path = path
            if cursor:
                separator = "&" if "?" in request_path else "?"
                request_path += separator + "continue=" + urllib.parse.quote(cursor, safe="")
            document = self.request(request_path)
            items.extend(document.get("items", []))
            cursor = (document.get("metadata") or {}).get("continue", "")
            if not cursor:
                return items
        raise RuntimeError("Kubernetes list pagination exceeded 50 pages")


def cpu_milli(value) -> int:
    if not value:
        return 0
    value = str(value)
    if value.endswith("m"):
        return int(float(value[:-1]))
    if value.endswith("n"):
        return int(float(value[:-1]) / 1_000_000)
    if value.endswith("u"):
        return int(float(value[:-1]) / 1_000)
    return int(float(value) * 1000)


def safe_section(errors: list, name: str, fn):
    try:
        return {"status": "complete", "data": fn()}
    except Exception as exc:  # deliberate: a failed source becomes visible coverage
        message = "{}: {}".format(type(exc).__name__, exc)[:240]
        errors.append({"source": name, "error": message})
        return {"status": "partial", "error": message}


def controller_maps(namespace_data: dict) -> tuple[dict, dict]:
    replica_sets, jobs = {}, {}
    for ns, data in namespace_data.items():
        for rs in data.get("replicasets", []):
            meta = rs.get("metadata") or {}
            refs = meta.get("ownerReferences") or []
            owner = next((r for r in refs if r.get("controller")), None)
            if owner:
                replica_sets[(ns, meta.get("name"))] = (owner.get("kind", "Deployment"), owner.get("name"))
        for job in data.get("jobs", []):
            meta = job.get("metadata") or {}
            refs = meta.get("ownerReferences") or []
            owner = next((r for r in refs if r.get("controller")), None)
            if owner and owner.get("kind") == "CronJob":
                jobs[(ns, meta.get("name"))] = ("CronJob", owner.get("name"))
    return replica_sets, jobs


def pod_ready(pod: dict) -> bool:
    conditions = {(c.get("type")): c.get("status") for c in (pod.get("status") or {}).get("conditions", [])}
    return conditions.get("Ready") == "True"


def hygiene_summary(pods: list[dict]) -> dict:
    containers = missing = 0
    for pod in pods:
        for container in (pod.get("spec") or {}).get("containers", []):
            containers += 1
            limits = ((container.get("resources") or {}).get("limits") or {})
            if not limits.get("cpu") or not limits.get("memory"):
                missing += 1
    return {
        "containers_checked": containers,
        "containers_missing_cpu_or_memory_limit": missing,
        "finding_groups": 1 if missing else 0,
        "advisory_only": True,
    }


def node_headroom_watch(row: dict) -> bool:
    return (
        (row.get("cpu_commit_pct") or 0) >= 90
        or (row.get("max_pods_free_pct") is not None and row["max_pods_free_pct"] <= 10)
        or (row.get("pod_cidr_free_pct") is not None and row["pod_cidr_free_pct"] <= 10)
    )


def workload_inventory(namespace_data: dict) -> tuple[int, int, list]:
    eligible = unavailable = 0
    details = []
    for ns, data in namespace_data.items():
        for kind, field in (("Deployment", "deployments"), ("StatefulSet", "statefulsets"), ("DaemonSet", "daemonsets")):
            for item in data.get(field, []):
                spec, status = item.get("spec") or {}, item.get("status") or {}
                if kind == "DaemonSet":
                    desired, ready = status.get("desiredNumberScheduled", 0), status.get("numberReady", 0)
                else:
                    desired, ready = spec.get("replicas", 0), status.get("readyReplicas", 0)
                if desired <= 0:
                    continue
                eligible += 1
                if ready < desired:
                    unavailable += 1
                    details.append({"namespace": ns, "kind": kind, "name": (item.get("metadata") or {}).get("name"), "ready": ready, "desired": desired})
    return eligible, unavailable, details


def domain(status: str, reasons: list[str], metrics: dict | None = None) -> dict:
    return {"status": status, "reasons": reasons, "metrics": metrics or {}}


def fox_symptom_family(check: str, reason: str) -> str:
    """Map Fox's per-finding vocabulary onto stable cluster symptom families."""
    check, reason = (check or "").lower(), (reason or "").lower()
    if reason in {"failedscheduling", "failed-scheduling", "pending-too-long"}:
        return "scheduling"
    if check in {"restart-rate"}:
        return "restart"
    if check in {"log-pattern"}:
        return "application_error"
    if check in {"resource-usage"} or "oom" in reason or "memory" in reason:
        return "resource_pressure"
    if check in {"service"}:
        return "networking"
    if check in {"pvc"}:
        return "storage"
    if check in {"scaling"}:
        return "scaling"
    if check in {"custom-resource"}:
        return "reconciliation"
    if check in {"resource-spec"}:
        return "hygiene"
    if check in {"workload", "pod-health", "event"}:
        return "availability"
    return "other"


def fox_state_findings(namespace_data: dict, cluster: str, replica_sets: dict, jobs: dict) -> tuple[dict, list[dict], dict]:
    """Normalize active Fox state without trusting pod-name finding identity."""
    pod_lookup = {
        ((pod.get("metadata") or {}).get("namespace"), (pod.get("metadata") or {}).get("name")): pod
        for namespace in namespace_data.values()
        for pod in namespace.get("pods", [])
    }
    summary = {
        "expected_namespaces": len(namespace_data),
        "complete_namespaces": 0,
        "missing_namespaces": [],
        "invalid_namespaces": [],
        "ongoing_findings": 0,
        "invalid_findings": 0,
        "findings_truncated": False,
        "stable_groups": 0,
    }
    normalized = []
    impacts: dict[str, str] = {}
    impact_domain = {
        "scheduling": "nodes_scheduling",
        "availability": "workload_availability",
        "scaling": "workload_availability",
        "networking": "workload_availability",
        "storage": "workload_availability",
        "reconciliation": "workload_availability",
        "resource_pressure": "resource_pressure",
        "application_error": "resource_pressure",
        "restart": "resource_pressure",
    }
    for namespace, data in namespace_data.items():
        status = data.get("fox_state_status", "missing")
        if status != "complete":
            target = summary["missing_namespaces"] if status == "missing" else summary["invalid_namespaces"]
            target.append(namespace)
            continue
        summary["complete_namespaces"] += 1
        state = data.get("fox_state") or {}
        findings = state.get("findings") or {}
        if not isinstance(findings, dict):
            summary["invalid_findings"] += 1
            continue
        rows = sorted(findings.items(), key=lambda row: str(row[0]))
        if len(rows) > 5000:
            rows = rows[:5000]
            summary["findings_truncated"] = True
        for finding_id, finding in rows:
            if not isinstance(finding, dict):
                summary["invalid_findings"] += 1
                continue
            if finding.get("status") != "ongoing":
                continue
            kind = str(finding.get("kind") or "Unknown")[:80]
            raw_name = str(finding.get("name") or "unknown")[:253]
            object_name = raw_name.split("/", 1)[0]
            if not NAME_RE.fullmatch(object_name) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9.]*", kind):
                summary["invalid_findings"] += 1
                continue
            classification = str(finding.get("classification") or "unknown")[:40]
            if classification not in {"healthy", "watch", "suspicious", "degraded", "incident-likely", "unknown"}:
                summary["invalid_findings"] += 1
                continue
            try:
                score = max(0, min(100, int(finding.get("score", 0) or 0)))
            except (TypeError, ValueError):
                summary["invalid_findings"] += 1
                continue
            summary["ongoing_findings"] += 1
            if kind == "Pod":
                pod = pod_lookup.get((namespace, object_name))
                owner = stable_owner(pod, replica_sets, jobs) if pod else {
                    "kind": "Pod", "name": object_name, "resolved": False,
                }
            else:
                owner = {"kind": kind, "name": object_name, "resolved": kind != "Unknown"}
            check = str(finding.get("check") or "unknown")[:80]
            reason = str(finding.get("reason") or "unknown")[:80]
            family = fox_symptom_family(check, reason)
            normalized.append({
                "key": problem_key(cluster, namespace, owner, family),
                "namespace": namespace,
                "owner": owner,
                "symptom_family": family,
                "detail": {
                    "source": "fox-autonomous-monitor",
                    "finding_id": str(finding_id)[:128],
                    "check": check,
                    "reason": reason,
                    "classification": classification,
                    "score": score,
                    "object_kind": kind,
                    "object_name": raw_name,
                },
            })
            domain_name = impact_domain.get(family)
            if domain_name:
                status_value = "degraded" if classification in {"degraded", "incident-likely"} else "watch"
                if STATUS_RANK[status_value] > STATUS_RANK.get(impacts.get(domain_name, "healthy"), 0):
                    impacts[domain_name] = status_value
    summary["stable_groups"] = len({finding["key"] for finding in normalized})
    return summary, normalized, impacts


def native_group_count(groups: dict, family: str) -> int:
    """Count only native groups for domain decisions; Fox is shadow evidence."""
    return sum(
        1 for group in groups.values()
        if group.get("symptom_family") == family
        and (group.get("source_counts") or {}).get("native", 0) > 0
    )


def collapse_fox_findings(findings: list[dict], native_keys: set[str], top_n: int) -> tuple[list[dict], bool]:
    """Keep Fox comparison groups bounded and outside authoritative problem groups."""
    grouped: dict[str, dict] = {}
    for finding in findings:
        key = finding["key"]
        entry = grouped.setdefault(key, {
            "key": key,
            "namespace": finding["namespace"],
            "owner": finding["owner"],
            "symptom_family": finding["symptom_family"],
            "finding_count": 0,
            "corroborates_native": key in native_keys,
            "examples": [],
        })
        entry["finding_count"] += 1
        if len(entry["examples"]) < 3:
            entry["examples"].append(finding["detail"])
    rows = sorted(grouped.values(), key=lambda row: row["key"])
    return rows[:top_n], len(rows) > top_n


def collect(api: Api, cfg: dict, previous: dict) -> dict:
    started = datetime.now(timezone.utc)
    errors: list[dict] = []
    raw = {}
    raw["readyz"] = safe_section(errors, "control_plane", lambda: api.request("/readyz?verbose", raw=True))
    raw["nodes"] = safe_section(errors, "nodes", lambda: api.list_items("/api/v1/nodes?limit=500"))

    namespace_data = {}
    resources = {
        "pods": "/api/v1/namespaces/{}/pods?limit=5000",
        "events": "/api/v1/namespaces/{}/events?limit=2000",
        "pvcs": "/api/v1/namespaces/{}/persistentvolumeclaims?limit=1000",
        "deployments": "/apis/apps/v1/namespaces/{}/deployments?limit=1000",
        "statefulsets": "/apis/apps/v1/namespaces/{}/statefulsets?limit=1000",
        "daemonsets": "/apis/apps/v1/namespaces/{}/daemonsets?limit=1000",
        "replicasets": "/apis/apps/v1/namespaces/{}/replicasets?limit=2000",
        "jobs": "/apis/batch/v1/namespaces/{}/jobs?limit=2000",
        "cronjobs": "/apis/batch/v1/namespaces/{}/cronjobs?limit=1000",
    }
    coverage_by_ns = {}
    for ns in cfg["namespaces"]:
        namespace_data[ns] = {}
        failures = []
        for name, path in resources.items():
            try:
                namespace_data[ns][name] = api.list_items(path.format(urllib.parse.quote(ns)))
            except Exception as exc:
                failures.append(name)
                errors.append({"source": "{}/{}".format(ns, name), "error": "{}: {}".format(type(exc).__name__, exc)[:240]})
        fox_status = "disabled"
        if cfg["fox_mesh_mode"] != "disabled":
            state_path = "/api/v1/namespaces/{}/configmaps/{}".format(
                urllib.parse.quote(ns), urllib.parse.quote(cfg["fox_state_configmap"])
            )
            try:
                fox_configmap = api.request(state_path)
                raw_state = (fox_configmap.get("data") or {}).get("state.json")
                if not raw_state:
                    raise ValueError("state.json is absent")
                fox_state = json.loads(raw_state)
                if fox_state.get("version") != 1 or fox_state.get("namespace") not in (None, "", ns):
                    raise ValueError("state identity/version does not match")
                namespace_data[ns]["fox_state"] = fox_state
                fox_status = "complete"
            except urllib.error.HTTPError as exc:
                fox_status = "missing" if exc.code == 404 else "error"
                errors.append({"source": "{}/fox_state".format(ns), "error": "HTTP {}".format(exc.code)})
            except Exception as exc:
                fox_status = "invalid"
                errors.append({"source": "{}/fox_state".format(ns), "error": "{}: {}".format(type(exc).__name__, exc)[:240]})
            namespace_data[ns]["fox_state_status"] = fox_status
        coverage_by_ns[ns] = {
            "status": "complete" if not failures else "partial",
            "failed_sources": failures,
            "fox_mesh": fox_status,
        }

    replica_sets, jobs = controller_maps(namespace_data)
    nodes = raw["nodes"].get("data", []) if raw["nodes"]["status"] == "complete" else []
    all_pods = [pod for data in namespace_data.values() for pod in data.get("pods", [])]
    active_pods = [pod for pod in all_pods if not is_successful_job_pod(pod)]

    requested_by_node = defaultdict(int)
    pods_by_node = Counter()
    for pod in active_pods:
        node_name = (pod.get("spec") or {}).get("nodeName")
        if node_name:
            pods_by_node[node_name] += 1
            for container in (pod.get("spec") or {}).get("containers", []):
                requested_by_node[node_name] += cpu_milli((((container.get("resources") or {}).get("requests") or {}).get("cpu")))

    node_metrics, node_findings = [], []
    for item in nodes:
        meta, spec, status = item.get("metadata") or {}, item.get("spec") or {}, item.get("status") or {}
        name = meta.get("name", "unknown")
        conditions = {c.get("type"): c for c in status.get("conditions", [])}
        ready = (conditions.get("Ready") or {}).get("status") == "True"
        pressure = [x for x in ("MemoryPressure", "DiskPressure", "PIDPressure") if (conditions.get(x) or {}).get("status") == "True"]
        alloc_cpu = cpu_milli((status.get("allocatable") or {}).get("cpu"))
        placement_complete = cfg["pod_placement_coverage"] == "full"
        cpu_commit = round(100 * requested_by_node[name] / alloc_cpu, 1) if placement_complete and alloc_cpu else None
        max_pods = int((status.get("allocatable") or {}).get("pods", 0) or 0)
        max_pods_free = round(100 * max(max_pods - pods_by_node[name], 0) / max_pods, 1) if placement_complete and max_pods else None
        cidr = spec.get("podCIDR")
        cidr_free = None
        cidr_status = "unavailable_partial_placement_coverage" if not placement_complete else "unavailable_cni_or_node_data"
        if placement_complete and cidr:
            try:
                capacity = max(ipaddress.ip_network(cidr, strict=False).num_addresses - 2, 1)
                cidr_free = round(100 * max(capacity - pods_by_node[name], 0) / capacity, 1)
                cidr_status = "available"
            except ValueError:
                pass
        unavailable_reason = "unavailable_partial_placement_coverage" if not placement_complete else "unavailable_node_data"
        row = {"node": name, "ready": ready, "unschedulable": bool(spec.get("unschedulable")), "pressure": pressure, "cpu_commit_status": "available" if cpu_commit is not None else unavailable_reason, "cpu_commit_pct": cpu_commit, "max_pods_headroom_status": "available" if max_pods_free is not None else unavailable_reason, "max_pods_free_pct": max_pods_free, "pod_cidr_headroom_status": cidr_status, "pod_cidr_free_pct": cidr_free}
        node_metrics.append(row)
        if not ready or spec.get("unschedulable") or pressure:
            node_findings.append(row)

    now = datetime.now(timezone.utc)
    event_cutoff = now - timedelta(minutes=cfg["event_window_minutes"])
    allowed_events, excluded_events, excluded_event_series, excluded_event_lifetime = [], Counter(), Counter(), Counter()
    undated = 0
    pod_lookup = {((p.get("metadata") or {}).get("namespace"), (p.get("metadata") or {}).get("name")): p for p in all_pods}
    groups = {}

    def add_group(ns, owner, family, detail, source="native"):
        key = problem_key(cfg["cluster"], ns, owner, family)
        existed = key in groups
        entry = groups.setdefault(key, {"key": key, "namespace": ns, "owner": owner, "symptom_family": family, "count": 0, "source_counts": {}, "examples": []})
        entry["source_counts"][source] = entry["source_counts"].get(source, 0) + 1
        # Fox corroboration must not double-count the same native observation.
        if source == "native" or not existed:
            entry["count"] += 1
        if len(entry["examples"]) < cfg["top_n"]:
            entry["examples"].append(detail)

    unhealthy_candidates = []
    oom_recent = restart_total = restart_delta = restart_resets = restart_first_seen = 0
    previous_restarts = previous.get("restart_observations") or {}
    restart_observations = {}
    hygiene = hygiene_summary(active_pods)
    for pod in active_pods:
        meta, spec, status = pod.get("metadata") or {}, pod.get("spec") or {}, pod.get("status") or {}
        ns, pod_name = meta.get("namespace", "unknown"), meta.get("name", "unknown")
        owner = stable_owner(pod, replica_sets, jobs)
        pending = status.get("phase") == "Pending"
        ready = pod_ready(pod)
        symptoms = []
        timing = {}
        if pending:
            symptoms.append("Pending")
            created = parse_k8s_timestamp(meta.get("creationTimestamp"))
            timing["pending_seconds"] = int((now - created).total_seconds()) if created else None
        if status.get("phase") == "Running" and not ready:
            symptoms.append("NotReady")
            ready_condition = next((c for c in status.get("conditions", []) if c.get("type") == "Ready"), {})
            transitioned = parse_k8s_timestamp(ready_condition.get("lastTransitionTime"))
            timing["not_ready_seconds"] = int((now - transitioned).total_seconds()) if transitioned else None
        restarts = 0
        for cs in status.get("containerStatuses", []) or []:
            container_name = cs.get("name", "unknown")
            observation_key = "{}/{}".format(meta.get("uid") or "{}/{}".format(ns, pod_name), container_name)
            current_restarts = int(cs.get("restartCount", 0) or 0)
            restarts += current_restarts
            if len(restart_observations) < cfg["max_state_observations"]:
                restart_observations[observation_key] = current_restarts
            delta, delta_status = counter_delta(current_restarts, previous_restarts.get(observation_key))
            restart_delta += delta
            if delta_status == "counter_reset":
                restart_resets += 1
            elif delta_status == "first_observation":
                restart_first_seen += 1
            terminated = ((cs.get("lastState") or {}).get("terminated") or {})
            if recent_termination(terminated, "OOMKilled", event_cutoff):
                oom_recent += 1
        restart_total += restarts
        if symptoms:
            add_group(ns, owner, "scheduling", {"pod": pod_name, "symptoms": symptoms, "timing": timing})
        if symptoms or restarts:
            unhealthy_candidates.append((pod, owner))

    previous_events = previous.get("event_observations") or {}
    event_observations = {}
    event_counter_resets = event_first_seen = 0
    for ns, data in namespace_data.items():
        for event in data.get("events", []):
            if event.get("type") != "Warning":
                continue
            ts = event_timestamp(event)
            if ts is None:
                undated += 1
                continue
            if ts < event_cutoff:
                continue
            reason = event.get("reason") or "Unknown"
            event_uid = (event.get("metadata") or {}).get("uid") or "{}/{}/{}".format(ns, reason, (event.get("metadata") or {}).get("name", "unknown"))
            current_count = int(event.get("count", 1) or 1)
            if len(event_observations) < cfg["max_state_observations"]:
                event_observations[event_uid] = current_count
            event_delta, event_delta_status = counter_delta(current_count, previous_events.get(event_uid))
            if event_delta_status == "counter_reset":
                event_counter_resets += 1
            elif event_delta_status == "first_observation":
                event_first_seen += 1
            # A newly observed recent series contributes presence=1, not its
            # cumulative lifetime count. Subsequent polls use the true delta.
            observed_count = 1 if event_delta_status == "first_observation" else event_delta
            if reason not in ALLOWED_WARNING_REASONS:
                excluded_events[reason] += observed_count
                excluded_event_series[reason] += 1
                excluded_event_lifetime[reason] += current_count
                continue
            involved = event.get("involvedObject") or {}
            pod = pod_lookup.get((ns, involved.get("name"))) if involved.get("kind") == "Pod" else None
            owner = stable_owner(pod, replica_sets, jobs) if pod else {"kind": involved.get("kind", "Unknown"), "name": involved.get("name", "unknown"), "resolved": False}
            family = "scheduling" if reason == "FailedScheduling" else "availability"
            if observed_count:
                add_group(ns, owner, family, {"reason": reason, "observed_count": observed_count})
                allowed_events.append({"namespace": ns, "reason": reason, "observed_count": observed_count})

    log_scan = {"mode": "selective", "candidate_pods": len(unhealthy_candidates), "pods_scanned": 0, "containers_scanned": 0, "error_lines": 0, "read_failures": 0, "truncated": len(unhealthy_candidates) > cfg["max_log_pods"]}
    for pod, owner in unhealthy_candidates[:cfg["max_log_pods"]]:
        meta, spec = pod.get("metadata") or {}, pod.get("spec") or {}
        ns, pod_name = meta.get("namespace"), meta.get("name")
        log_scan["pods_scanned"] += 1
        for container in spec.get("containers", []):
            name = container.get("name")
            path = "/api/v1/namespaces/{}/pods/{}/log?container={}&sinceSeconds={}&tailLines=200".format(urllib.parse.quote(ns), urllib.parse.quote(pod_name), urllib.parse.quote(name), cfg["log_window_seconds"])
            try:
                text = api.request(path, raw=True)
                log_scan["containers_scanned"] += 1
                matches = sum(1 for line in text.splitlines() if ERROR_LINE.search(line))
                log_scan["error_lines"] += matches
                if matches:
                    add_group(ns, owner, "application_error", {"pod": pod_name, "container": name, "matching_lines": matches})
            except Exception as exc:
                log_scan["read_failures"] += 1
                errors.append({"source": "{}/{}/log".format(ns, pod_name), "error": "{}: {}".format(type(exc).__name__, exc)[:240]})

    eligible, unavailable, unavailable_details = workload_inventory(namespace_data)
    for row in unavailable_details:
        add_group(
            row["namespace"],
            {"kind": row["kind"], "name": row["name"], "resolved": True},
            "availability",
            {"ready": row["ready"], "desired": row["desired"]},
        )
    unavailable_share = (unavailable / eligible) if eligible else None
    critical_unavailable = any(row["namespace"] in cfg["critical_namespaces"] for row in unavailable_details)

    fox_summary, fox_findings, fox_impacts = fox_state_findings(
        namespace_data, cfg["cluster"], replica_sets, jobs
    ) if cfg["fox_mesh_mode"] != "disabled" else ({
        "expected_namespaces": 0,
        "complete_namespaces": 0,
        "missing_namespaces": [],
        "invalid_namespaces": [],
        "ongoing_findings": 0,
        "invalid_findings": 0,
        "findings_truncated": False,
        "stable_groups": 0,
    }, [], {})
    fox_summary["candidate_domain_impacts"] = fox_impacts
    fox_summary["groups"], fox_summary["groups_truncated"] = collapse_fox_findings(
        fox_findings, set(groups), cfg["top_n"]
    )

    readyz_ok = raw["readyz"]["status"] == "complete" and not any(line.startswith("[-]") for line in raw["readyz"].get("data", "").splitlines())
    node_critical = any(not row["ready"] for row in node_metrics)
    node_degraded = any(row["unschedulable"] or row["pressure"] for row in node_metrics)
    node_watch = any(node_headroom_watch(row) for row in node_metrics)
    scheduling_groups = native_group_count(groups, "scheduling")

    if node_critical:
        nodes_domain = domain("critical", ["one or more nodes are not Ready"])
    elif scheduling_groups or node_degraded:
        nodes_domain = domain("degraded", ["scheduling symptoms or node pressure present"])
    elif node_watch:
        nodes_domain = domain("watch", ["absolute node headroom threshold reached"])
    else:
        nodes_domain = domain("healthy", [])
    nodes_domain["metrics"] = {"nodes": len(node_metrics), "scheduling_groups": scheduling_groups}

    if critical_unavailable or (unavailable_share is not None and unavailable_share > 0.10):
        workload_domain = domain("critical", ["critical service unavailable or over 10% of eligible workloads unavailable"])
    elif unavailable:
        workload_domain = domain("degraded", ["a nonzero share of eligible workloads is unavailable"])
    elif eligible == 0:
        workload_domain = domain("watch", ["no eligible controllers were observed"])
    else:
        workload_domain = domain("healthy", [])
    workload_domain["metrics"] = {"eligible_workloads": eligible, "unavailable_workloads": unavailable, "unavailable_share": unavailable_share}

    shared_bad = [row for row in unavailable_details if row["namespace"] in cfg["critical_namespaces"]]
    shared_domain = domain("critical" if shared_bad else ("healthy" if readyz_ok else "degraded"), ["critical namespace workload unavailable"] if shared_bad else ([] if readyz_ok else ["control-plane readiness check failed"]))
    shared_domain["metrics"] = {"critical_namespace_failures": len(shared_bad), "control_plane_ready": readyz_ok}

    pressure_status = "degraded" if oom_recent or log_scan["error_lines"] else ("watch" if restart_delta else "healthy")
    pressure_domain = domain(pressure_status, ["recent OOM or selected error-log evidence"] if pressure_status == "degraded" else (["container restart delta observed"] if pressure_status == "watch" else []), {"recent_oom": oom_recent, "container_restart_total": restart_total, "container_restart_delta": restart_delta, "restart_counter_resets": restart_resets, "restart_first_observations": restart_first_seen, "selected_error_lines": log_scan["error_lines"]})

    required_complete = raw["readyz"]["status"] == "complete" and raw["nodes"]["status"] == "complete" and all(value["status"] == "complete" for value in coverage_by_ns.values())
    delivery_domain = domain("healthy" if required_complete else "degraded", [] if required_complete else ["one or more required API sources are unavailable"], {"api_errors": len(errors)})
    domains = {"nodes_scheduling": nodes_domain, "workload_availability": workload_domain, "shared_services": shared_domain, "resource_pressure": pressure_domain, "delivery": delivery_domain}
    gate = evaluate_gate(domains, required_complete, previous.get("gate"))

    seq = int(previous.get("seq", 0)) + 1
    ended = datetime.now(timezone.utc)
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "cluster_id": cfg["cluster"],
        "source_generation": cfg["generation"],
        "snapshot_seq": seq,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "completed_at": ended.isoformat().replace("+00:00", "Z"),
        "policy_version": POLICY_VERSION,
        "baseline_version": BASELINE_VERSION,
        "triage_mode": "report_only",
        "display_score": display_score(domains),
        "domains": domains,
        "gate": gate,
        "coverage": {
            "complete": required_complete,
            "expected_namespaces": cfg["namespaces"],
            "namespaces": coverage_by_ns,
            "optional": {"metrics_api": "unavailable" if os.environ.get("METRICS_API_AVAILABLE", "false") != "true" else "available", "logs": "selective", "node_pod_capacity": "available" if cfg["pod_placement_coverage"] == "full" else "unavailable_partial_placement_coverage", "fox_mesh": cfg["fox_mesh_mode"]},
            "errors": errors[:cfg["top_n"]],
            "error_count": len(errors),
        },
        "aggregates": {
            "nodes": node_metrics,
            "workloads": {"eligible": eligible, "unavailable": unavailable, "unavailable_examples": unavailable_details[:cfg["top_n"]], "membership_complete": required_complete},
            "events": {"allowlist_version": ALLOWED_WARNING_REASONS_VERSION, "included": sum(row["observed_count"] for row in allowed_events), "excluded_observed_total": sum(excluded_events.values()), "excluded_observed_by_reason": dict(excluded_events.most_common(cfg["top_n"])), "excluded_series_total": sum(excluded_event_series.values()), "excluded_series_by_reason": dict(excluded_event_series.most_common(cfg["top_n"])), "excluded_lifetime_count_visible_only": sum(excluded_event_lifetime.values()), "excluded_lifetime_by_reason_visible_only": dict(excluded_event_lifetime.most_common(cfg["top_n"])), "undated": undated, "counter_resets": event_counter_resets, "first_observations": event_first_seen},
            "logs": log_scan,
            "hygiene": hygiene,
            "fox_mesh": fox_summary,
            "completed_job_pods_excluded": sum(1 for pod in all_pods if is_successful_job_pod(pod)),
        },
        "problem_groups": sorted(groups.values(), key=lambda group: group["key"])[:cfg["top_n"]],
        "problem_group_total": len(groups),
        "problem_groups_truncated": len(groups) > cfg["top_n"],
        "membership_complete": required_complete,
        "collector_cost": {"api_calls": api.calls, "api_response_bytes": api.response_bytes, "api_duration_ms": round(api.duration_ms, 1), "poll_duration_ms": round((ended - started).total_seconds() * 1000, 1), "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "api_calls_by_scope": dict(api.calls_by_scope), "api_response_bytes_by_scope": dict(api.bytes_by_scope)},
        "state": {
            "restart_observations": len(restart_observations),
            "event_observations": len(event_observations),
            "observations_pruned": len(set(previous_restarts) - set(restart_observations)) + len(set(previous_events) - set(event_observations)),
            "trend_coverage": "partial" if len(restart_observations) >= cfg["max_state_observations"] or len(event_observations) >= cfg["max_state_observations"] else "complete",
        },
        "_restart_observations": restart_observations,
        "_event_observations": event_observations,
    }
    return snapshot


def get_optional(api: Api, path: str) -> dict:
    try:
        return api.request(path)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        raise


def previous_pointer(api: Api) -> dict:
    cm = get_optional(api, "/api/v1/namespaces/{}/configmaps/{}".format(STATE_NAMESPACE, POINTER_NAME))
    raw = (cm.get("data") or {}).get("pointer.json")
    return json.loads(raw) if raw else {}


def create_configmap(api: Api, name: str, labels: dict, key: str, document: dict, immutable: bool = True):
    body = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name, "namespace": STATE_NAMESPACE, "labels": labels}, "immutable": immutable, "data": {key: json.dumps(document, sort_keys=True, separators=(",", ":"))}}
    return api.request("/api/v1/namespaces/{}/configmaps".format(STATE_NAMESPACE), method="POST", body=body)


def update_pointer(api: Api, pointer: dict, exists: bool):
    body = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": POINTER_NAME, "namespace": STATE_NAMESPACE, "labels": {"app.kubernetes.io/name": "cluster-health-assessment", "app.kubernetes.io/component": "state"}}, "data": {"pointer.json": json.dumps(pointer, sort_keys=True, separators=(",", ":"))}}
    path = "/api/v1/namespaces/{}/configmaps".format(STATE_NAMESPACE)
    if exists:
        current = api.request(path + "/" + POINTER_NAME)
        body["metadata"]["resourceVersion"] = (current.get("metadata") or {}).get("resourceVersion")
        return api.request(path + "/" + POINTER_NAME, method="PUT", body=body)
    return api.request(path, method="POST", body=body)


def gc(api: Api, retain: int):
    selector = urllib.parse.quote("cluster-health.platform/snapshot=true")
    items = api.request("/api/v1/namespaces/{}/configmaps?labelSelector={}".format(STATE_NAMESPACE, selector)).get("items", [])
    items.sort(key=lambda cm: (cm.get("metadata") or {}).get("creationTimestamp", ""), reverse=True)
    for cm in items[retain:]:
        name = (cm.get("metadata") or {}).get("name")
        api.request("/api/v1/namespaces/{}/configmaps/{}".format(STATE_NAMESPACE, name), method="DELETE")


def enforce_size(snapshot: dict, max_bytes: int, top_n: int) -> dict:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) <= max_bytes:
        return snapshot
    snapshot["problem_groups"] = snapshot["problem_groups"][:max(1, top_n // 4)]
    snapshot["problem_groups_truncated"] = True
    snapshot["coverage"]["errors"] = snapshot["coverage"]["errors"][:5]
    snapshot["aggregates"]["workloads"]["unavailable_examples"] = snapshot["aggregates"]["workloads"]["unavailable_examples"][:5]
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > max_bytes:
        raise RuntimeError("aggregate snapshot exceeds configured size cap")
    return snapshot


def finalize_snapshot(snapshot: dict, max_bytes: int) -> dict:
    snapshot["serialized_bytes"] = 0
    for _ in range(3):
        snapshot["checksum"] = canonical_checksum(snapshot)
        snapshot["serialized_bytes"] = len(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())
    snapshot["checksum"] = canonical_checksum(snapshot)
    final_size = len(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())
    if final_size > max_bytes:
        raise RuntimeError("final snapshot exceeds configured size cap")
    snapshot["serialized_bytes"] = final_size
    snapshot["checksum"] = canonical_checksum(snapshot)
    return snapshot


def run_snapshot(api: Api, cfg: dict):
    previous = previous_pointer(api)
    snapshot = collect(api, cfg, previous)
    restart_observations = snapshot.pop("_restart_observations", {})
    event_observations = snapshot.pop("_event_observations", {})
    snapshot = enforce_size(snapshot, cfg["max_bytes"], cfg["top_n"])
    snapshot = finalize_snapshot(snapshot, cfg["max_bytes"])
    name = SNAPSHOT_PREFIX + str(snapshot["snapshot_seq"]).zfill(10)
    labels = {"app.kubernetes.io/name": "cluster-health-assessment", "app.kubernetes.io/component": "snapshot", "cluster-health.platform/snapshot": "true", "cluster-health.platform/coverage": "complete" if snapshot["coverage"]["complete"] else "partial"}
    create_configmap(api, name, labels, "snapshot.json", snapshot)
    pointer = {"seq": snapshot["snapshot_seq"], "snapshot": name, "checksum": snapshot["checksum"], "completed_at": snapshot["completed_at"], "display_score": snapshot["display_score"], "gate": snapshot["gate"], "coverage_complete": snapshot["coverage"]["complete"], "restart_observations": restart_observations, "event_observations": event_observations}
    update_pointer(api, pointer, bool(previous))
    gc(api, cfg["retain"])
    print(json.dumps({"snapshot": name, "score": snapshot["display_score"], "coverage_complete": snapshot["coverage"]["complete"], "gate": snapshot["gate"], "cost": snapshot["collector_cost"]}, indent=2))


def run_report(api: Api):
    pointer = previous_pointer(api)
    if not pointer.get("snapshot"):
        raise RuntimeError("no snapshot is available")
    snapshot_cm = api.request("/api/v1/namespaces/{}/configmaps/{}".format(STATE_NAMESPACE, pointer["snapshot"]))
    snapshot = json.loads((snapshot_cm.get("data") or {})["snapshot.json"])
    tz = ZoneInfo("Europe/London")
    now = datetime.now(tz)
    override = os.environ.get("REPORT_SLOT_OVERRIDE", "").strip()
    if override:
        slot = override
        timing = "manual"
    else:
        scheduled_hour = 7 if now.hour < 12 else 16
        slot_name = "morning" if scheduled_hour == 7 else "evening"
        slot = "{}-{}".format(now.strftime("%Y%m%d"), slot_name)
        scheduled = now.replace(hour=scheduled_hour, minute=30, second=0, microsecond=0)
        delay = max(0, int((now - scheduled).total_seconds()))
        timing = "on_time" if delay <= 60 else ("late" if delay <= 1800 else "missed")
    report = {"schema_version": 1, "report_slot": slot, "timing": timing, "timezone": "Europe/London", "generated_at": now.isoformat(), "snapshot_ref": pointer["snapshot"], "snapshot_checksum": pointer["checksum"], "snapshot_completed_at": pointer["completed_at"], "display_score": snapshot["display_score"], "domains": snapshot["domains"], "gate": snapshot["gate"], "coverage": snapshot["coverage"], "top_problem_groups": snapshot["problem_groups"][:10], "triage_mode": "report_only"}
    name = REPORT_PREFIX + re.sub(r"[^a-z0-9-]", "-", slot.lower())[:45]
    labels = {"app.kubernetes.io/name": "cluster-health-assessment", "app.kubernetes.io/component": "report", "cluster-health.platform/report": "true", "cluster-health.platform/timing": timing}
    try:
        create_configmap(api, name, labels, "report.json", report)
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
    print(json.dumps(report, indent=2))


def main():
    try:
        cfg = load_config()
        if not cfg["cluster"] or not cfg["generation"]:
            raise ValueError("CLUSTER_ID and SOURCE_GENERATION are required")
        api = Api()
        mode = os.environ.get("MODE", "snapshot")
        if mode == "snapshot":
            run_snapshot(api, cfg)
        elif mode == "report":
            run_report(api)
        else:
            raise ValueError("MODE must be snapshot or report")
    except Exception as exc:
        print("cluster-health-assessment failed: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
