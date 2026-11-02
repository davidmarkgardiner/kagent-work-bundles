"""Strict, metadata-only recovery receipts; consistency is not authentication."""
import json
from pathlib import Path
import re
import time

LIMIT = 64 * 1024
IDENT = r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}"
NAME = r"[a-z0-9][a-z0-9.-]{0,252}"
SHA = r"(?:[0-9a-f]{40}|[0-9a-f]{64})"
HASH = r"[0-9a-f]{64}"
POLICY_OBSERVATION_METHOD = "stable-read-and-admission-probes"
OBSERVATION_FIELDS = ("observationMethod", "activeProbeGeneration")
OPTIONAL_FIELDS = {
    "liveObject": OBSERVATION_FIELDS,
    "probes": (*OBSERVATION_FIELDS, "policyReadBefore", "policyReadAfter"),
    "verification": OBSERVATION_FIELDS,
}
BINDING = ("profileRevision", "incidentId", "runId", "clusterId", "namespace",
           "policyName", "ruleName", "application", "taskId")
STAGES = (
    ("fault", "Admission fault"), ("investigation", "Native investigation"),
    ("proposal", "Repository fix"), ("ci", "Exact-head CI"),
    ("review", "Independent review"), ("approval", "Human approval"),
    ("merge", "Merge"), ("gitops", "GitOps sync"),
    ("liveObject", "Live policy readback"), ("probes", "Admission recovery"),
    ("application", "Application recovery"), ("verification", "Native verification"),
)
TELEMETRY = ("investigation", "model", "skill", "knowledge", "kubernetes-mcp",
             "gitlab-mcp", "verification", "gateway")
FIELDS = {
    "fault": ("policyRevision", "policySpecSha256", "observations", "application"),
    "investigation": ("taskState",),
    "proposal": ("projectId", "mergeRequestIid", "headSha", "policyPath", "policySpecSha256"),
    "review": ("headSha", "reviewerId", "result"),
    "ci": ("headSha", "pipelineId", "result", "validAdmission", "invalidAdmission"),
    "approval": ("headSha", "approverId", "principalType", "decision"),
    "merge": ("headSha", "mergeRequestIid", "mergeSha", "result"),
    "gitops": ("sourceRevision", "appliedRevision", "ready"),
    "liveObject": ("uid", "generation", "observedGeneration", "policySpecSha256", "enforcement", "ready", "deleting"),
    "probes": ("observedGeneration", "policySpecSha256", "observations"),
    "application": ("namespace", "deploymentName", "uid", "deploymentObservedAt", "generation", "observedGeneration", "desiredReplicas", "actualReplicas", "updatedReplicas", "readyReplicas", "availableReplicas", "unavailableReplicas", "httpObservations"),
    "verification": ("taskId", "parentTaskId", "taskState", "result", "mergeSha", "policySpecSha256", "observedGeneration", "probeReceiptId", "applicationReceiptId", "applicationUid", "applicationGeneration", "traceId", "spanId"),
}


class InvalidMetadata(ValueError):
    pass


def obj(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise InvalidMetadata("Unexpected or missing metadata fields")
    return value


def text(value, pattern=IDENT):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise InvalidMetadata("Invalid metadata identifier")
    return value


def integer(value, minimum=1, maximum=2**53 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise InvalidMetadata("Invalid metadata number")
    return value


def binding(value):
    obj(value, BINDING)
    for key in BINDING:
        text(value[key], HASH if key == "profileRevision" else NAME if key in {"namespace", "policyName", "ruleName", "application"} else IDENT)


def policy_path(value):
    text(value, r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise InvalidMetadata("Invalid policy path")


def profile(value):
    obj(value, ("schemaVersion", "mode", "observerId", "binding", "agent", "repository",
                "reviewerId", "humanApproverId", "healthyPolicySpecSha256", "mcpServices", "maxAgeSeconds", "application"), ("verificationTaskId",))
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 or value["mode"] not in {"live", "fixture"}:
        raise InvalidMetadata("Unsupported recovery profile")
    binding(value["binding"])
    if "verificationTaskId" in value:
        text(value["verificationTaskId"])
    for key in ("observerId", "reviewerId", "humanApproverId"):
        text(value[key])
    obj(value["agent"], ("namespace", "name"))
    for item in value["agent"].values():
        text(item, NAME)
    if value["reviewerId"] in {value["agent"]["name"], value["agent"]["namespace"] + "/" + value["agent"]["name"]} or value["humanApproverId"] in {value["agent"]["name"], value["agent"]["namespace"] + "/" + value["agent"]["name"]}:
        raise InvalidMetadata("Agent cannot approve its own recovery")
    obj(value["repository"], ("projectId", "policyPath"))
    text(value["repository"]["projectId"])
    policy_path(value["repository"]["policyPath"])
    text(value["healthyPolicySpecSha256"], HASH)
    obj(value["application"], ("namespace", "deploymentName", "expectedStatus", "expectedBodySha256"))
    for key in ("namespace", "deploymentName"):
        text(value["application"][key], NAME)
    if value["application"]["namespace"] != value["binding"]["namespace"]:
        raise InvalidMetadata("Application is outside the incident namespace")
    integer(value["application"]["expectedStatus"], 200, 299)
    text(value["application"]["expectedBodySha256"], HASH)
    obj(value["mcpServices"], ("kubernetes", "gitlab"))
    for item in value["mcpServices"].values():
        text(item)
    integer(value["maxAgeSeconds"], 30, 300)
    return value


def probe_list(value, fault=False):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise InvalidMetadata("Invalid probe window")
    ids, previous = set(), 0
    for probe in value:
        obj(probe, ("probeId", "observedAt", "kind", "result"))
        text(probe["probeId"])
        integer(probe["observedAt"])
        if (probe["probeId"] in ids or probe["observedAt"] < previous
                or probe["kind"] not in ({"valid"} if fault else {"valid", "invalid"})
                or probe["result"] not in {"admitted", "denied", "error"}):
            raise InvalidMetadata("Invalid probe observation")
        ids.add(probe["probeId"])
        previous = probe["observedAt"]


def reference(value):
    obj(value, ("traceId", "spanId"))
    for key, length in (("traceId", 32), ("spanId", 16)):
        text(value[key], rf"[0-9a-f]{{{length}}}")
        if int(value[key], 16) == 0:
            raise InvalidMetadata("Zero OTel identifier")


def blocked_application(value):
    obj(value, ("namespace", "deploymentName", "uid", "observedAt", "generation", "observedGeneration", "desiredReplicas", "updatedReplicas", "availableReplicas"))
    for key, item in value.items():
        if key in {"namespace", "deploymentName"}:
            text(item, NAME)
        elif key == "uid":
            text(item)
        else:
            integer(item, 0 if key.endswith("Replicas") and key != "desiredReplicas" else 1)


def http_probes(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise InvalidMetadata("Invalid HTTP probe window")
    ids, previous = set(), 0
    for probe in value:
        obj(probe, ("probeId", "observedAt", "statusCode", "bodySha256"))
        text(probe["probeId"])
        text(probe["bodySha256"], HASH)
        integer(probe["observedAt"])
        integer(probe["statusCode"], 0, 599)
        if probe["probeId"] in ids or probe["observedAt"] < previous:
            raise InvalidMetadata("Invalid HTTP observation")
        ids.add(probe["probeId"])
        previous = probe["observedAt"]


def policy_read(value):
    """Exact metadata projection from an actual policy read, without status inference."""
    obj(value, ("uid", "generation", "policy_spec_sha256", "ready", "deleting", "enforcement", "observed_at"))
    text(value["uid"])
    integer(value["generation"])
    text(value["policy_spec_sha256"], HASH)
    integer(value["observed_at"])
    text(value["enforcement"])
    if type(value["ready"]) is not bool or type(value["deleting"]) is not bool:
        raise InvalidMetadata("Invalid policy-read boolean")


def policy_generation_matches(receipt, live):
    if live.get("observedGeneration") is None:
        return (receipt["observedGeneration"] is None
                and all(r.get("observationMethod") == POLICY_OBSERVATION_METHOD
                        and r.get("activeProbeGeneration") == live.get("generation") for r in (receipt, live)))
    return (live["observedGeneration"] == live.get("generation")
            and receipt["observedGeneration"] == live.get("generation")
            and all(r.get("observationMethod", "native-observed-generation") == "native-observed-generation"
                    and r.get("activeProbeGeneration") is None for r in (receipt, live)))


def policy_bracket_matches(receipt, live):
    reads = (receipt.get("policyReadBefore"), receipt.get("policyReadAfter"))
    times = [p["observedAt"] for p in receipt["observations"]]
    return (all(isinstance(r, dict) and r["uid"] == live.get("uid")
                and r["generation"] == live.get("generation")
                and r["policy_spec_sha256"] == live.get("policySpecSha256")
                and r["ready"] is True and r["deleting"] is False and r["enforcement"] == "Enforce"
                for r in reads)
            and reads[0]["observed_at"] <= min(times) <= max(times) <= reads[1]["observed_at"] <= receipt["recordedAt"])


def snapshot(value):
    obj(value, ("schemaVersion", "mode", "observerId", "binding", "capturedAt", "summary", "receipts", "telemetry"))
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 or value["mode"] not in {"live", "fixture"}:
        raise InvalidMetadata("Unsupported recovery snapshot")
    text(value["observerId"])
    binding(value["binding"])
    integer(value["capturedAt"])
    obj(value["summary"], ("fault", "fix"))
    for item in value["summary"].values():
        text(item, r"[^\x00-\x1f\x7f]{1,240}")
    obj(value["receipts"], (), FIELDS)
    receipt_ids = set()
    for key, receipt in value["receipts"].items():
        obj(receipt, ("receiptId", "binding", "recordedAt", *FIELDS[key]), OPTIONAL_FIELDS.get(key, ()))
        text(receipt["receiptId"])
        if receipt["receiptId"] in receipt_ids:
            raise InvalidMetadata("Duplicate receipt identity")
        receipt_ids.add(receipt["receiptId"])
        binding(receipt["binding"])
        integer(receipt["recordedAt"])
        for field in FIELDS[key]:
            item = receipt[field]
            if field == "observations":
                probe_list(item, fault=key == "fault")
            elif field == "application":
                blocked_application(item)
            elif field == "httpObservations":
                http_probes(item)
            elif field in {"generation", "observedGeneration", "mergeRequestIid", "applicationGeneration", "deploymentObservedAt", "desiredReplicas"}:
                if not (field == "observedGeneration" and key in OPTIONAL_FIELDS and item is None):
                    integer(item)
            elif field.endswith("Replicas"):
                integer(item, 0)
            elif field in {"ready", "deleting"}:
                if type(item) is not bool:
                    raise InvalidMetadata("Invalid metadata boolean")
            elif field.endswith("Sha256"):
                text(item, HASH)
            elif field in {"headSha", "mergeSha", "policyRevision", "sourceRevision", "appliedRevision"}:
                text(item, SHA)
            elif field == "policyPath":
                policy_path(item)
            else:
                text(item)
        for field in OPTIONAL_FIELDS.get(key, ()):
            if field not in receipt:
                continue
            if field.startswith("policyRead"):
                policy_read(receipt[field])
            elif field == "activeProbeGeneration":
                if receipt[field] is not None:
                    integer(receipt[field])
            else:
                text(receipt[field])
        if key == "verification":
            reference({field: receipt[field] for field in ("traceId", "spanId")})
    obj(value["telemetry"], (), TELEMETRY)
    for ref in value["telemetry"].values():
        reference(ref)
    return value


def unknown(reason, enabled=True):
    return {"enabled": enabled, "state": "unknown", "label": "Recovery unknown",
            "reasons": [reason], "stages": [], "telemetry": {"state": "incomplete", "checks": []},
            "completeDemoProof": False}


def task_ids(span):
    attrs = span.get("attributes", {})
    return {attrs[key] for key in ("a2a.task.id", "gen_ai.task.id") if attrs.get(key)}


def joined_span(ref, activity, plan, task_id=None):
    trace = next((item for item in activity.get("traces", []) if item["traceId"] == ref["traceId"]), None)
    if trace is None:
        return None
    span = next((item for item in trace["spans"] if item["spanId"] == ref["spanId"]), None)
    if span is None:
        return None
    expected, agent = plan["binding"], plan["agent"]
    task_id = task_id or expected["taskId"]
    attrs = span.get("attributes", {})
    if any(attrs.get(key, expected[field]) != expected[field] for key, field in
           (("flow.incident.id", "incidentId"), ("flow.run.id", "runId"))):
        return None
    if task_ids(span) - {task_id}:
        return None
    if not task_ids(span) and any(task_ids(item) - {task_id} for item in trace["spans"]):
        return None
    native = trace.get("nativeRuntimeIdentity") or {}
    native_anchor = (native.get("agentId") == agent["namespace"] + "/" + agent["name"]
                     and any(s.get("component") == "kagent" and task_ids(s) == {task_id}
                             for s in trace["spans"]))
    explicit_backend = (task_ids(span) == {task_id}
                        and attrs.get("flow.incident.id") == expected["incidentId"]
                        and attrs.get("flow.run.id") == expected["runId"])
    if not (native_anchor or explicit_backend):
        return None
    return trace, span


def telemetry_view(data, activity, plan):
    checks = []
    for category in TELEMETRY:
        ref = data["telemetry"].get(category)
        task_id = plan.get("verificationTaskId", plan["binding"]["taskId"]) if category == "verification" else plan["binding"]["taskId"]
        joined = joined_span(ref, activity, plan, task_id) if ref else None
        valid = False
        if joined:
            trace, span = joined
            attrs = span.get("attributes", {})
            native = ((trace.get("nativeRuntimeIdentity") or {}).get("agentId") ==
                      plan["agent"]["namespace"] + "/" + plan["agent"]["name"]
                      and span.get("component") == "kagent" and task_ids(span) == {task_id})
            tool = attrs.get("gen_ai.tool.name") or attrs.get("mcp.tool.name") or attrs.get("tool.name")
            if category in {"investigation", "verification"}:
                valid = native
            elif category == "model":
                valid = any(call["spanId"] == span["spanId"] for call in trace.get("modelCalls", []))
            elif category == "gateway":
                valid = span.get("component") == "agentgateway" and span.get("kind") == "server"
            elif category in {"skill", "knowledge"}:
                names = {"load_skill", "skills"} if category == "skill" else {"load_skill_resource", "read_file"}
                valid = native and span.get("toolCategory") == "skill" and span.get("toolExecution") == "native-skill" and tool in names
            else:
                service = plan["mcpServices"]["kubernetes" if category == "kubernetes-mcp" else "gitlab"]
                valid = (span.get("service") == service and span.get("toolCategory") == "mcp"
                         and span.get("toolExecution") in {"server", "kagent-tools-internal"})
            valid = valid and span.get("otelStatus") != "error" and attrs.get("flow.simulated") is not True
        checks.append({"category": category, "state": "observed" if valid else "unknown",
                       "reason": "Exact retained trace/span and task binding" if valid else "Matching execution span is not retained or does not match",
                       **(ref if valid else {})})
    return {"state": "complete" if all(item["state"] == "observed" for item in checks) else "incomplete", "checks": checks}


def project_recovery(plan, data, activity=None, now=None):
    """Pure reducer. Only the external observer can establish receipt authenticity."""
    now = time.time() if now is None else now
    try:
        profile(plan)
        snapshot(data)
    except (InvalidMetadata, TypeError):
        return unknown("Recovery metadata failed strict validation")
    if (data["binding"] != plan["binding"] or data["observerId"] != plan["observerId"] or data["mode"] != plan["mode"]):
        return {**unknown("Snapshot does not match the independently configured profile"), "state": "blocked", "label": "Recovery blocked"}
    age = plan["maxAgeSeconds"]
    if not data["capturedAt"] <= now < data["capturedAt"] + age:
        return unknown("Snapshot is stale or from the future")
    receipts = data["receipts"]
    telemetry = telemetry_view(data, activity or {}, plan)
    stages, previous = [], 0
    head = receipts.get("proposal", {}).get("headSha")
    merge = receipts.get("merge", {}).get("mergeSha")
    healthy = plan["healthyPolicySpecSha256"]
    live = receipts.get("liveObject", {})
    probes = receipts.get("probes", {})
    application = receipts.get("application", {})

    def gate(key, receipt):
        if receipt["binding"] != plan["binding"]:
            return "blocked", "Receipt incident, run, profile, target or task does not match"
        if not previous <= receipt["recordedAt"] <= data["capturedAt"]:
            return "blocked", "Receipt order or observation time does not match"
        if key == "fault":
            observations = receipt["observations"]
            times = [p["observedAt"] for p in observations]
            app, target = receipt["application"], plan["application"]
            ok = (len(times) >= 3 and len(set(times)) >= 3 and 60 <= max(times) - min(times) <= 120
                  and all(p["result"] == "denied" for p in observations)
                  and max(times) <= receipt["recordedAt"] and receipt["policySpecSha256"] != healthy
                  and (app["namespace"], app["deploymentName"]) == (target["namespace"], target["deploymentName"])
                  and min(times) <= app["observedAt"] <= receipt["recordedAt"]
                  and (app["updatedReplicas"] < app["desiredReplicas"] or app["availableReplicas"] < app["desiredReplicas"]))
            return ("passed", "Repeated known-good denials and a blocked application rollout") if ok else ("blocked", "Policy-specific fault and blocked application rollout are not established")
        if key == "investigation":
            ok = receipt["taskState"] == "accepted"
        elif key == "proposal":
            ok = (receipt["projectId"] == plan["repository"]["projectId"] and receipt["policyPath"] == plan["repository"]["policyPath"] and receipt["policySpecSha256"] == healthy)
        elif key == "review":
            ok = receipt["headSha"] == head and receipt["reviewerId"] == plan["reviewerId"] and receipt["result"] == "approved"
        elif key == "ci":
            ok = receipt["headSha"] == head and (receipt["result"], receipt["validAdmission"], receipt["invalidAdmission"]) == ("passed", "admitted", "denied")
        elif key == "approval":
            ok = (receipt["headSha"] == head and receipt["approverId"] == plan["humanApproverId"] and receipt["principalType"] == "human" and receipt["decision"] == "approved")
        elif key == "merge":
            ok = receipt["headSha"] == head and receipt["mergeRequestIid"] == receipts.get("proposal", {}).get("mergeRequestIid") and receipt["result"] == "merged"
        elif key == "gitops":
            ok = receipt["sourceRevision"] == receipt["appliedRevision"] == merge and receipt["ready"]
        elif key == "liveObject":
            if not receipt["recordedAt"] <= now < receipt["recordedAt"] + age:
                return "unknown", "Live policy readback is stale or from the future"
            ok = (policy_generation_matches(receipt, live) and receipt["policySpecSha256"] == healthy
                  and receipt["enforcement"] == "Enforce" and receipt["ready"] and not receipt["deleting"])
        elif key == "probes":
            observations = receipt["observations"]
            if any(not p["observedAt"] <= now < p["observedAt"] + age for p in observations):
                return "unknown", "Admission probe window is stale or from the future"
            active_proof = live.get("observedGeneration") is None
            if active_proof and any(not r["observed_at"] <= now < r["observed_at"] + age
                                    for r in (receipt.get("policyReadBefore"), receipt.get("policyReadAfter")) if r):
                return "unknown", "Admission policy bracket is stale or from the future"
            positives = [p["observedAt"] for p in observations if p["kind"] == "valid"]
            negatives = [p["observedAt"] for p in observations if p["kind"] == "invalid" and p["result"] == "denied"]
            ok = (len(positives) >= 3 and len(set(positives)) >= 3 and 60 <= max(positives) - min(positives) <= 120
                  and bool(negatives) and max(negatives) >= max(positives)
                  and all(live.get("recordedAt", now + 1) <= p["observedAt"] <= receipt["recordedAt"] for p in observations)
                  and all(p["result"] == ("admitted" if p["kind"] == "valid" else "denied") for p in observations)
                  and policy_generation_matches(receipt, live) and receipt["policySpecSha256"] == healthy
                  and (not active_proof or policy_bracket_matches(receipt, live)))
            return ("passed", "Three valid admissions passed; invalid admission remains denied") if ok else ("blocked", "Recovery probes failed, are incomplete, or no longer enforce the policy")
        elif key == "application":
            observations, target = receipt["httpObservations"], plan["application"]
            if (not receipt["deploymentObservedAt"] <= now < receipt["deploymentObservedAt"] + age
                    or any(not p["observedAt"] <= now < p["observedAt"] + age for p in observations)):
                return "unknown", "Application rollout or HTTP observations are stale or from the future"
            times = [p["observedAt"] for p in observations]
            failed = receipts.get("fault", {}).get("application", {})
            ok = ((receipt["namespace"], receipt["deploymentName"]) == (target["namespace"], target["deploymentName"])
                  and receipt["uid"] == failed.get("uid") and receipt["generation"] >= failed.get("generation", 2**53)
                  and receipt["generation"] == receipt["observedGeneration"] and receipt["unavailableReplicas"] == 0
                  and all(receipt[field] == receipt["desiredReplicas"] for field in ("actualReplicas", "updatedReplicas", "readyReplicas", "availableReplicas"))
                  and live.get("recordedAt", now + 1) <= receipt["deploymentObservedAt"] <= min(times) <= max(times) <= receipt["recordedAt"]
                  and len(times) >= 3 and len(set(times)) >= 3 and 60 <= max(times) - min(times) <= 120
                  and all(p["statusCode"] == target["expectedStatus"] and p["bodySha256"] == target["expectedBodySha256"] for p in observations))
            return ("passed", "Current application rollout and three exact HTTP responses verified") if ok else ("blocked", "Application rollout or expected HTTP response has not recovered")
        else:
            ref = {key: receipt[key] for key in ("traceId", "spanId")}
            ok = (receipt["taskState"] == "completed" and receipt["result"] == "recovered" and receipt["mergeSha"] == merge
                  and receipt["parentTaskId"] == plan["binding"]["taskId"]
                  and receipt["taskId"] == plan.get("verificationTaskId", plan["binding"]["taskId"])
                  and receipt["policySpecSha256"] == healthy and policy_generation_matches(receipt, live)
                  and receipt["probeReceiptId"] == probes.get("receiptId")
                  and receipt["applicationReceiptId"] == application.get("receiptId")
                  and receipt["applicationUid"] == application.get("uid") and receipt["applicationGeneration"] == application.get("generation"))
            if ok:
                if plan["mode"] == "fixture":
                    return "passed", "Fixture receipt replay only; live native completion is unverified"
                verification = next(item for item in telemetry["checks"] if item["category"] == "verification")
                if data["telemetry"].get("verification") != ref or verification["state"] != "observed":
                    return "unknown", "Native verification task has no matching retained span"
                joined = joined_span(ref, activity or {}, plan, receipt["taskId"])
                ended = int(joined[1]["endNs"]) / 1_000_000_000
                if not max(probes["recordedAt"], application["recordedAt"]) <= ended <= receipt["recordedAt"] + 1:
                    return "blocked", "Native verification span does not follow the recovery observations"
                state = joined[1].get("attributes", {}).get("a2a.task.state")
                if state and state not in {"completed", "TASK_STATE_COMPLETED"}:
                    return "blocked", "Native task telemetry contradicts completed verification"
        return ("passed", "Matching observer receipt") if ok else ("blocked", "Receipt does not match the reviewed recovery chain")

    for key, label in STAGES:
        receipt = receipts.get(key)
        state, reason = gate(key, receipt) if receipt else ("unknown", "No observer receipt")
        stages.append({"key": key, "label": label, "state": state, "reason": reason,
                       **({"recordedAt": receipt["recordedAt"]} if receipt else {})})
        if receipt:
            previous = max(previous, receipt["recordedAt"])
    failures = [item for item in stages if item["state"] != "passed"]
    state = "blocked" if any(item["state"] == "blocked" for item in failures) else "unknown" if failures else "replay-passed" if plan["mode"] == "fixture" else "recovered"
    return {"enabled": True, "state": state,
            "label": {"blocked": "Recovery blocked", "unknown": "Recovery unknown", "recovered": "Recovery verified", "replay-passed": "Fixture replay passed"}[state],
            "mode": plan["mode"], "binding": data["binding"], "summary": data["summary"],
            "verificationTaskId": plan.get("verificationTaskId", plan["binding"]["taskId"]),
            "observerId": plan["observerId"], "capturedAt": data["capturedAt"],
            "expiresAt": min([data["capturedAt"] + age] + [r["recordedAt"] + age for key, r in receipts.items() if key == "liveObject"]
                             + [p["observedAt"] + age for p in probes.get("observations", [])]
                             + [probes[key]["observed_at"] + age for key in ("policyReadBefore", "policyReadAfter")
                                if live.get("observedGeneration") is None and key in probes]
                             + ([application["deploymentObservedAt"] + age] if application else [])
                             + [p["observedAt"] + age for p in application.get("httpObservations", [])]),
            "repository": {**plan["repository"], "mergeRequestIid": receipts.get("proposal", {}).get("mergeRequestIid"), "headSha": head, "mergeSha": merge},
            "reasons": [item["label"] + ": " + item["reason"] for item in failures], "stages": stages, "telemetry": telemetry,
            "completeDemoProof": state == "recovered" and telemetry["state"] == "complete"}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InvalidMetadata("Duplicate JSON key")
        value[key] = item
    return value


def reject_constant(_value):
    raise InvalidMetadata("Invalid JSON number")


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise InvalidMetadata("Recovery file exceeds 64 KiB")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def read_view(snapshot_path=None, profile_path=None, activity=None, now=None):
    if not snapshot_path and not profile_path:
        return unknown("Recovery observer is not configured", enabled=False)
    if not snapshot_path or not profile_path:
        return unknown("Both a reviewed recovery profile and observer snapshot are required")
    try:
        return project_recovery(read_json(profile_path), read_json(snapshot_path), activity, now)
    except (OSError, ValueError, TypeError, RecursionError):
        return unknown("Recovery files are unreadable or failed strict validation")
