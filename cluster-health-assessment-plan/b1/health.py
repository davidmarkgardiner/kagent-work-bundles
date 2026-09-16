"""Pure health-assessment policy used by the B1 collector and tests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

DOMAIN_ORDER = (
    "nodes_scheduling",
    "workload_availability",
    "shared_services",
    "resource_pressure",
    "delivery",
)
DOMAIN_WEIGHTS = {
    "nodes_scheduling": 0.30,
    "workload_availability": 0.25,
    "shared_services": 0.20,
    "resource_pressure": 0.15,
    "delivery": 0.10,
}
STATUS_VALUE = {"healthy": 100, "watch": 80, "degraded": 50, "critical": 0}
STATUS_RANK = {"healthy": 0, "watch": 1, "degraded": 2, "critical": 3}


def display_score(domains: dict) -> int:
    """Return the non-authoritative weighted display score."""
    return round(
        sum(DOMAIN_WEIGHTS[name] * STATUS_VALUE[domains[name]["status"]]
            for name in DOMAIN_ORDER)
    )


def evaluate_gate(domains: dict, coverage_complete: bool, previous: dict | None = None) -> dict:
    """Evaluate admission/recovery without using the display score.

    Critical is immediate, even with another unknown domain. Degraded requires
    two consecutive complete assessments. Recovery requires two consecutive
    complete assessments with every domain healthy or watch.
    """
    previous = previous or {}
    prior_active = bool(previous.get("active", False))
    any_critical = any(domains[name]["status"] == "critical" for name in DOMAIN_ORDER)
    any_degraded = any(domains[name]["status"] == "degraded" for name in DOMAIN_ORDER)
    all_recovery_eligible = all(
        STATUS_RANK[domains[name]["status"]] <= STATUS_RANK["watch"]
        for name in DOMAIN_ORDER
    )

    degraded_streak = (
        int(previous.get("degraded_streak", 0)) + 1
        if coverage_complete and any_degraded else 0
    )
    recovery_streak = (
        int(previous.get("recovery_streak", 0)) + 1
        if coverage_complete and all_recovery_eligible else 0
    )

    active = prior_active
    transition = "none"
    reason = "holding previous gate state"
    if any_critical:
        active = True
        reason = "at least one required domain is critical"
        if not prior_active:
            transition = "breach"
    elif prior_active:
        if recovery_streak >= 2:
            active = False
            transition = "recovery"
            reason = "two complete recovery-eligible assessments"
        elif not coverage_complete:
            reason = "coverage incomplete; recovery blocked"
        elif not all_recovery_eligible:
            reason = "breach remains active; one or more domains are degraded"
        else:
            reason = "recovery confirmation pending"
    elif coverage_complete and degraded_streak >= 2:
        active = True
        transition = "breach"
        reason = "degraded domain persisted for two complete assessments"
    elif not coverage_complete:
        reason = "coverage incomplete; degraded admission blocked"
    elif any_degraded:
        reason = "first complete degraded assessment; confirmation pending"
    else:
        reason = "all required domains are healthy or watch"

    return {
        "active": active,
        "transition": transition,
        "reason": reason,
        "degraded_streak": degraded_streak,
        "recovery_streak": recovery_streak,
        "coverage_complete": coverage_complete,
    }


def canonical_checksum(document: dict) -> str:
    unsigned = dict(document)
    unsigned.pop("checksum", None)
    body = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def parse_k8s_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def event_timestamp(event: dict) -> datetime | None:
    for field in ("eventTime", "lastTimestamp", "firstTimestamp"):
        parsed = parse_k8s_timestamp(event.get(field))
        if parsed is not None:
            return parsed
    return parse_k8s_timestamp((event.get("series") or {}).get("lastObservedTime"))


def stable_owner(pod: dict, replica_sets: dict, jobs: dict) -> dict:
    """Resolve a pod to a stable controller, preserving unresolved identity."""
    meta = pod.get("metadata") or {}
    namespace = meta.get("namespace", "unknown")
    pod_name = meta.get("name", "unknown")
    refs = meta.get("ownerReferences") or []
    if not refs:
        return {"kind": "Pod", "name": pod_name, "resolved": False}
    owner = next((ref for ref in refs if ref.get("controller")), refs[0])
    kind, name = owner.get("kind", "Unknown"), owner.get("name", pod_name)
    if kind == "ReplicaSet":
        parent = replica_sets.get((namespace, name))
        if parent:
            return {"kind": parent[0], "name": parent[1], "resolved": True}
        return {"kind": kind, "name": name, "resolved": False}
    if kind == "Job":
        parent = jobs.get((namespace, name))
        if parent:
            return {"kind": parent[0], "name": parent[1], "resolved": True}
        return {"kind": kind, "name": name, "resolved": True}
    return {"kind": kind, "name": name, "resolved": kind != "Pod"}


def problem_key(cluster: str, namespace: str, owner: dict, symptom_family: str) -> str:
    return "/".join((cluster, namespace, owner["kind"], owner["name"], symptom_family))


def is_successful_job_pod(pod: dict) -> bool:
    phase = (pod.get("status") or {}).get("phase")
    refs = (pod.get("metadata") or {}).get("ownerReferences") or []
    return phase == "Succeeded" and any(ref.get("kind") == "Job" for ref in refs)


def counter_delta(current: int, previous: int | None) -> tuple[int, str]:
    """Return a rolling counter delta with explicit first/reset coverage."""
    current = max(0, int(current or 0))
    if previous is None:
        return 0, "first_observation"
    previous = max(0, int(previous or 0))
    if current < previous:
        return 0, "counter_reset"
    return current - previous, "complete"


def recent_termination(termination: dict, reason: str, cutoff: datetime) -> bool:
    if termination.get("reason") != reason:
        return False
    finished = parse_k8s_timestamp(termination.get("finishedAt"))
    return finished is not None and finished >= cutoff
