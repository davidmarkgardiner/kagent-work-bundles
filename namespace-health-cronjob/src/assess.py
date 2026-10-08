"""Pure namespace-health rules and bounded report construction."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

SCHEMA = "namespace-health.report.v1"
MAX_REPORT = 8192
BLOCKING = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError"}
ERROR_VALUES = {"error", "err", "fatal", "critical"}


def when(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.astimezone(timezone.utc) if date.tzinfo else None
    except (ValueError, TypeError):
        return None


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def age_at(value, now, seconds):
    date = when(value)
    return date is not None and date <= now - timedelta(seconds=seconds) and date <= now + timedelta(minutes=5)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def event_seen(event, now):
    dates = [when((event.get("series") or {}).get("lastObservedTime")), when(event.get("lastTimestamp")), when(event.get("eventTime"))]
    return max((d for d in dates if d and d <= now + timedelta(minutes=5)), default=None)


def owner(pod, rs_by_uid, jobs_by_uid):
    refs = pod.get("metadata", {}).get("ownerReferences") or []
    ref = next((r for r in refs if r.get("controller")), refs[0] if refs else None)
    if not ref:
        return {"kind": "Pod", "name": "unresolved", "resolved": False}
    if ref.get("kind") == "ReplicaSet":
        rs = rs_by_uid.get(ref.get("uid"))
        parent = next((r for r in (rs or {}).get("metadata", {}).get("ownerReferences", []) if r.get("controller") and r.get("kind") == "Deployment"), None)
        if parent:
            return {"kind": "Deployment", "name": parent["name"], "resolved": True}
    if ref.get("kind") == "Job":
        job = jobs_by_uid.get(ref.get("uid"))
        parent = next((r for r in (job or {}).get("metadata", {}).get("ownerReferences", []) if r.get("controller") and r.get("kind") == "CronJob"), None)
        if parent:
            return {"kind": "CronJob", "name": parent["name"], "resolved": True}
    resolved = ref.get("kind") not in {"ReplicaSet", "Job"} or ref.get("uid") in (rs_by_uid if ref.get("kind") == "ReplicaSet" else jobs_by_uid)
    return {"kind": ref.get("kind", "Unknown")[:32], "name": ref.get("name", "unknown")[:63] if resolved else "unresolved", "resolved": resolved}


def ref(kind, name, resolved=True):
    return {"kind": kind[:32], "name": name[:63], "resolved": resolved}


def add(findings, rule, score, workload, count=1):
    row = next((f for f in findings if f["rule_id"] == rule), None)
    if row is None:
        row = {"rule_id": rule, "risk_tier": score, "observed_count": 0, "workloads": []}
        findings.append(row)
    row["observed_count"] += count
    if workload not in row["workloads"] and len(row["workloads"]) < 3:
        row["workloads"].append(workload)


def inspect_log(data, start, now):
    """Count only complete timestamped JSON application records inside the window."""
    errors, lines, first, last = 0, 0, None, None
    for raw in data.splitlines():
        if len(raw) > 8192:
            continue
        try:
            timestamp, body = raw.split(b" ", 1)
            observed = when(timestamp.decode("ascii"))
            if observed is None or observed < start or observed > now + timedelta(minutes=5):
                continue
            record = json.loads(body)
            if not isinstance(record, dict):
                continue
            lines += 1
            first = min(first, observed) if first else observed
            last = max(last, observed) if last else observed
            if str(record.get("severity", record.get("level", ""))).lower() in ERROR_VALUES:
                errors += 1
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {"errors": errors, "lines": lines, "first": iso(first) if first else None, "last": iso(last) if last else None}


def assess_namespace(snapshot, log_samples, policy, now, window_start):
    meta = snapshot["namespace"]["metadata"]
    findings = []
    critical = set(policy.get("critical_workloads", {}).get(meta["name"], []))
    controllers = []
    for kind, key in (("Deployment", "deployments"), ("StatefulSet", "statefulsets"), ("DaemonSet", "daemonsets")):
        for c in snapshot.get(key, []):
            spec, stat, m = c.get("spec", {}), c.get("status", {}), c["metadata"]
            desired = spec.get("replicas", 1) if kind != "DaemonSet" else stat.get("desiredNumberScheduled", 0)
            available = stat.get("availableReplicas", stat.get("numberAvailable", 0)) or 0
            ready = stat.get("readyReplicas", stat.get("numberReady", 0)) or 0
            current = stat.get("observedGeneration", 0) >= m.get("generation", 1)
            identity = f"{kind}/{m['name']}"
            controllers.append((kind, m["name"], c))
            if desired > 0 and current and available == 0 and identity in critical:
                add(findings, "critical_zero_available", 100, ref(kind, m["name"]))
            if kind == "Deployment" and desired > available and current:
                for cond in stat.get("conditions", []):
                    if cond.get("type") == "Available" and cond.get("status") == "False" and age_at(cond.get("lastTransitionTime"), now, 300):
                        add(findings, "deployment_available_false_5m", 90, ref(kind, m["name"]))
                        break
            if desired > 0 and current and ready == 0 and age_at(m.get("creationTimestamp"), now, 600):
                add(findings, "zero_ready_after_startup_grace_duration_unknown", 80, ref(kind, m["name"]))
    rs_by_uid = {x["metadata"]["uid"]: x for x in snapshot.get("replicasets", [])}
    jobs_by_uid = {x["metadata"]["uid"]: x for x in snapshot.get("jobs", [])}
    pod_owners = {}
    for pod in snapshot.get("pods", []):
        m, state = pod["metadata"], pod.get("status", {})
        if m.get("deletionTimestamp"):
            continue
        identity = owner(pod, rs_by_uid, jobs_by_uid)
        pod_owners[m["uid"]] = identity
        if state.get("phase") in {"Succeeded", "Failed"}:
            continue
        pcond = {x.get("type"): x for x in state.get("conditions", [])}
        scheduled = pcond.get("PodScheduled", {})
        if state.get("phase") == "Pending" and scheduled.get("status") == "False" and scheduled.get("reason") == "Unschedulable" and age_at(scheduled.get("lastTransitionTime"), now, 600):
            add(findings, "pod_unschedulable_10m", 80, identity)
        ready = pcond.get("Ready", {})
        if ready.get("status") != "False" or not age_at(ready.get("lastTransitionTime"), now, 300):
            continue
        statuses = state.get("containerStatuses", []) + state.get("initContainerStatuses", [])
        blocked = any((cs.get("state", {}).get("waiting") or {}).get("reason") in BLOCKING or (cs in state.get("initContainerStatuses", []) and cs.get("state", {}).get("waiting")) for cs in statuses)
        if blocked:
            add(findings, "pod_not_ready_blocked_5m", 90, identity)
    for job in snapshot.get("jobs", []):
        cond = next((c for c in job.get("status", {}).get("conditions", []) if c.get("type") == "Failed" and c.get("status") == "True"), None)
        if cond and (at := when(cond.get("lastTransitionTime"))) and window_start <= at <= now + timedelta(minutes=5):
            refs = job["metadata"].get("ownerReferences") or []
            parent = next((r for r in refs if r.get("kind") == "CronJob"), None)
            add(findings, "recent_terminal_job_failure", 80, ref("CronJob", parent["name"]) if parent else ref("Job", job["metadata"]["name"]))
    errors_by_owner = {}
    for sample in log_samples:
        pod = sample["pod"]
        if pod["metadata"].get("deletionTimestamp"):
            continue
        ident = pod_owners.get(pod["metadata"]["uid"], ref("Pod", pod["metadata"]["name"], False))
        key = (ident["kind"], ident["name"])
        errors_by_owner[key] = errors_by_owner.get(key, 0) + sample["summary"]["errors"]
    for (kind, name), count in errors_by_owner.items():
        if count >= 20:
            add(findings, "sampled_application_errors_20", 80, ref(kind, name), count)
    warnings = [e for e in snapshot.get("events", []) if e.get("type") == "Warning" and (seen := event_seen(e, now)) and window_start <= seen <= now]
    if warnings:
        add(findings, "recent_warning_context", 60, ref("Event", "typed-warning"), len(warnings))
    findings.sort(key=lambda f: (-f["risk_tier"], f["rule_id"]))
    risk = max((f["risk_tier"] for f in findings), default=0)
    affected = {(w["kind"], w["name"]) for f in findings if f["risk_tier"] == risk for w in f["workloads"]}
    return {"uid": meta["uid"], "name": meta["name"], "risk_tier": risk, "affected_workload_count": len(affected), "findings": findings[:3]}


def make_report(cluster, source_generation, policy_version, scheduled, started, ended, window_start, rows, coverage, threshold=80, watched_count=None):
    if scheduled.second or scheduled.microsecond:
        raise ValueError("scheduled occurrence must have minute precision")
    eligible = sorted((r for r in rows if r["risk_tier"] >= threshold), key=lambda r: (-r["risk_tier"], -r["affected_workload_count"], r["uid"]))
    selected = eligible[:3]
    status = "investigate" if selected else "unknown" if coverage["required_failed"] else "no_breach_observed"
    slot = digest([cluster, iso(scheduled)])
    stable = {"status": status, "source_generation": source_generation, "policy_version": policy_version, "namespaces": [{"uid": n["uid"], "risk_tier": n["risk_tier"], "findings": [{"rule_id": f["rule_id"], "workloads": sorted(f["workloads"], key=lambda x: (x["kind"], x["name"]))} for f in n["findings"]]} for n in selected]}
    report = {"schema": SCHEMA, "cluster": cluster, "source_generation": source_generation, "policy_version": policy_version, "slot_id": slot, "scheduled_at": iso(scheduled), "assessment_started_at": iso(started), "assessment_ended_at": iso(ended), "window_started_at": iso(window_start), "status": status, "automation_allowed": False, "threshold": threshold, "namespaces": selected, "watched_namespace_count": watched_count if watched_count is not None else len(rows), "assessed_namespace_count": coverage["assessed"], "eligible_namespace_count": len(eligible), "qualifying_namespaces_omitted": max(0, len(eligible)-3), "coverage": coverage, "finding_digest": digest(stable)}
    report["payload_digest"] = digest(report)
    if len(canonical(report)) > MAX_REPORT:
        raise ValueError("report exceeds 8 KiB")
    return report


def validate_report(report, cluster=None, now=None):
    allowed = {"schema", "cluster", "source_generation", "policy_version", "slot_id", "scheduled_at", "assessment_started_at", "assessment_ended_at", "window_started_at", "status", "automation_allowed", "threshold", "namespaces", "watched_namespace_count", "assessed_namespace_count", "eligible_namespace_count", "qualifying_namespaces_omitted", "coverage", "finding_digest", "payload_digest"}
    if not isinstance(report, dict) or set(report) != allowed:
        raise ValueError("report field set invalid")
    for field in ("cluster", "source_generation", "policy_version"):
        if not isinstance(report[field], str) or not 1 <= len(report[field]) <= 80 or not re.fullmatch(r"[A-Za-z0-9_.-]+", report[field]):
            raise ValueError("invalid report identity")
    if not isinstance(report, dict) or report.get("schema") != SCHEMA or report.get("automation_allowed") is not False or report.get("status") not in {"investigate", "unknown", "no_breach_observed"}:
        raise ValueError("invalid report header")
    if cluster and report.get("cluster") != cluster:
        raise ValueError("wrong cluster")
    if len(canonical(report)) > MAX_REPORT or len(report.get("namespaces", [])) > 3:
        raise ValueError("report bounds exceeded")
    if not isinstance(report.get("threshold"), int) or not 60 <= report["threshold"] <= 100:
        raise ValueError("invalid threshold")
    for field in ("watched_namespace_count", "assessed_namespace_count", "eligible_namespace_count", "qualifying_namespaces_omitted"):
        if not isinstance(report.get(field), int) or not 0 <= report[field] <= 5:
            raise ValueError("invalid namespace count")
    if not 1 <= report["watched_namespace_count"] or report["assessed_namespace_count"] > report["watched_namespace_count"] or report["eligible_namespace_count"] > report["assessed_namespace_count"] or report["eligible_namespace_count"] < len(report["namespaces"]) or report["qualifying_namespaces_omitted"] != report["eligible_namespace_count"]-len(report["namespaces"]):
        raise ValueError("inconsistent namespace counts")
    coverage = report.get("coverage")
    coverage_fields = {"required_failed", "assessed", "failed_checks", "failure_sources", "rotation_cycle_hours_lower_bound", "log_candidates", "log_candidates_not_inspected", "unconfigured_containers", "allocated_log_reads", "completed_log_reads", "truncated_log_reads", "api_calls", "structured_api_bytes", "log_bytes", "sampling"}
    if not isinstance(coverage, dict) or set(coverage) != coverage_fields or not isinstance(coverage["required_failed"], bool) or coverage["sampling"] != "bounded" or coverage["assessed"] != report["assessed_namespace_count"]:
        raise ValueError("invalid coverage fields")
    for field, maximum in (("assessed",5),("failed_checks",60),("rotation_cycle_hours_lower_bound",1000),("log_candidates",1000),("log_candidates_not_inspected",1000),("unconfigured_containers",1000),("allocated_log_reads",24),("completed_log_reads",24),("truncated_log_reads",24),("api_calls",60),("structured_api_bytes",8*1024*1024),("log_bytes",3*1024*1024)):
        if not isinstance(coverage[field], int) or not 0 <= coverage[field] <= maximum:
            raise ValueError("invalid coverage count")
    if coverage["completed_log_reads"] > coverage["allocated_log_reads"] or not isinstance(coverage["failure_sources"], list) or len(coverage["failure_sources"]) > 8 or any(not isinstance(x,str) or len(x)>40 for x in coverage["failure_sources"]):
        raise ValueError("inconsistent coverage")
    if report["status"] == "unknown" and not coverage["required_failed"] or report["status"] == "no_breach_observed" and coverage["required_failed"]:
        raise ValueError("status contradicts coverage")
    at = when(report.get("scheduled_at"))
    if at is None or at.second or at.microsecond or report.get("slot_id") != digest([report.get("cluster"), iso(at)]):
        raise ValueError("invalid slot")
    now = now or datetime.now(timezone.utc)
    if at < now-timedelta(hours=2) or at > now+timedelta(minutes=5):
        raise ValueError("slot outside admission window")
    if report.get("payload_digest") != digest({k:v for k,v in report.items() if k != "payload_digest"}):
        raise ValueError("payload digest mismatch")
    for n in report["namespaces"]:
        if set(n) != {"uid", "name", "risk_tier", "affected_workload_count", "findings"} or not isinstance(n["uid"], str) or len(n["uid"]) > 80 or not isinstance(n["name"], str) or not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", n["name"]):
            raise ValueError("invalid namespace identity")
        if not isinstance(n.get("risk_tier"), int) or n["risk_tier"] < report.get("threshold", 80) or len(n.get("findings", [])) > 3:
            raise ValueError("invalid finding")
        for f in n["findings"]:
            if set(f) != {"rule_id", "risk_tier", "observed_count", "workloads"} or not isinstance(f["rule_id"], str) or not re.fullmatch(r"[a-z0-9_]{1,80}", f["rule_id"]):
                raise ValueError("invalid rule")
            if not isinstance(f["observed_count"], int) or f["observed_count"] < 0:
                raise ValueError("invalid count")
            for w in f["workloads"]:
                if set(w) != {"kind", "name", "resolved"} or len(w["kind"]) > 32 or len(w["name"]) > 63 or not isinstance(w["resolved"], bool):
                    raise ValueError("invalid workload reference")
            if len(f.get("workloads", [])) > 3:
                raise ValueError("too many workload references")
    if (report["status"] == "investigate") != bool(report["namespaces"]):
        raise ValueError("status/findings disagree")
    stable = {"status": report["status"], "source_generation": report["source_generation"], "policy_version": report["policy_version"], "namespaces": [{"uid": n["uid"], "risk_tier": n["risk_tier"], "findings": [{"rule_id": f["rule_id"], "workloads": sorted(f["workloads"], key=lambda x: (x["kind"], x["name"]))} for f in n["findings"]]} for n in report["namespaces"]]}
    if report.get("finding_digest") != digest(stable):
        raise ValueError("finding digest mismatch")
    return report
