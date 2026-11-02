"""Project actual operator receipts up to the human gate; never grant approval.

Inputs must come from the trusted observer. This checks consistency, not the
authenticity of externally supplied receipts. No API or model is called here.
"""
from datetime import datetime

from core import Config, Rejected


def timestamp(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def build(config, ledger, candidate, fault_application, initial_task, current_task, inspection, activity, now):
    c = Config.from_dict(config) if isinstance(config, dict) else config
    state, outbox = ledger["state"], ledger["outbox"]
    if state.get("human_authorization") or state.get("merged"):
        raise Rejected("Use the post-decision observer after a human decision or merge")
    task = initial_task.get("result", {}).get("task", initial_task.get("task", initial_task))
    if (outbox.get("status") != "accepted" or task.get("id") != outbox.get("task_id")
            or not any(m.get("messageId") == outbox["message_id"] for m in task.get("history", []))
            or candidate["candidate_id"] != outbox["candidate_id"]):
        raise Rejected("Actual accepted original-message binding is required")
    if (current_task.get("id") != task["id"] or current_task.get("contextId") != task.get("contextId")
            or current_task.get("status", {}).get("state") != "TASK_STATE_INPUT_REQUIRED"):
        raise Rejected("The same native task must actually be awaiting input")
    created_at = current_task.get("metadata", {}).get("kagent.dev/a2a/task-created-at")
    if not created_at:
        raise Rejected("Actual native task creation time is required")
    proposal = state.get("proposal")
    if not proposal or proposal["binding"] != inspection.get("binding") or not inspection.get("diff_valid"):
        raise Rejected("Exact recorded proposal and inspected diff are required")
    b = proposal["binding"]
    if (b["project_id"] != c.project_id or b["run_id"] != c.run_id or b["incident_id"] != c.incident_id
            or inspection.get("policy_spec_sha256") != c.healthy_policy_spec_sha256):
        raise Rejected("Proposal is outside the reviewed profile")
    binding = {"profileRevision": c.profile_revision, "incidentId": c.incident_id, "runId": c.run_id,
               "clusterId": c.cluster_id, "namespace": c.namespace, "policyName": c.policy_name,
               "ruleName": c.rule_name, "application": c.application, "taskId": task["id"]}
    ns, agent = c.investigator_id.split("/")
    plan = {"schemaVersion": 1, "mode": "live", "observerId": "kyverno-operator-observer", "binding": binding,
            "agent": {"namespace": ns, "name": agent}, "repository": {"projectId": c.project_id, "policyPath": c.policy_file},
            "reviewerId": c.reviewer_id, "humanApproverId": c.human_approver_id,
            "healthyPolicySpecSha256": c.healthy_policy_spec_sha256,
            "mcpServices": {"kubernetes": c.kubernetes_service, "gitlab": c.gitlab_service}, "maxAgeSeconds": 300,
            "application": {"namespace": c.namespace, "deploymentName": c.application,
                            "expectedStatus": c.expected_http_status, "expectedBodySha256": c.expected_body_sha256}}
    def receipt(name, at, **values):
        return {"receiptId": name + "-" + c.run_id, "binding": binding, "recordedAt": at, **values}
    observations = [{"probeId": p["probe"]["probe_id"], "observedAt": p["probe"]["observed_at"],
                     "kind": p["probe"]["kind"], "result": p["probe"]["result"]} for p in candidate["observations"]]
    observations.sort(key=lambda p: p["observedAt"])
    app = {k: fault_application[k] for k in ("namespace", "deploymentName", "uid", "observedAt", "generation",
                                            "observedGeneration", "desiredReplicas", "updatedReplicas", "availableReplicas")}
    fault_at = fault_application["recordedAt"]
    receipts = {
        "fault": receipt("fault", fault_at, policyRevision=candidate["observations"][-1]["policy"]["policy_revision"],
                         policySpecSha256=c.faulty_policy_spec_sha256, observations=observations, application=app),
        "investigation": receipt("investigation", timestamp(created_at), taskState="accepted"),
        "proposal": receipt("proposal", proposal["created_at"], projectId=c.project_id, mergeRequestIid=b["iid"],
                            headSha=b["head_sha"], policyPath=c.policy_file, policySpecSha256=c.healthy_policy_spec_sha256),
    }
    if inspection.get("ci_pass"):
        receipts["ci"] = receipt("ci", timestamp(inspection["pipeline"]["updated_at"]), headSha=b["head_sha"],
                                 pipelineId=str(inspection["pipeline"]["id"]), result="passed",
                                 validAdmission="admitted", invalidAdmission="denied")
    review = state.get("review")
    if review:
        if review.get("binding") != b or review.get("reviewer_id") != c.reviewer_id or review.get("verdict") != "PASS":
            raise Rejected("Independent review does not match this exact head")
        receipts["review"] = receipt("review", review["reviewed_at"], headSha=b["head_sha"],
                                     reviewerId=c.reviewer_id, result="approved")
    refs = {}
    for trace in activity.get("traces", []):
        if (trace.get("nativeRuntimeIdentity") or {}).get("agentId") != c.investigator_id:
            continue
        if not any(s.get("component") == "kagent" and s.get("attributes", {}).get("a2a.task.id") == task["id"]
                   for s in trace.get("spans", [])):
            continue
        model_spans = {call["spanId"] for call in trace.get("modelCalls", [])}
        for span in trace["spans"]:
            attrs = span.get("attributes", {})
            tool = attrs.get("gen_ai.tool.name") or attrs.get("mcp.tool.name") or attrs.get("tool.name")
            ref = {"traceId": trace["traceId"], "spanId": span["spanId"]}
            native = span.get("component") == "kagent" and attrs.get("a2a.task.id") == task["id"]
            if native and span["name"].startswith("invoke_agent "):
                refs.setdefault("investigation", ref)
            if span["spanId"] in model_spans:
                refs.setdefault("model", ref)
            if native and span.get("toolExecution") == "native-skill":
                if tool == "load_skill":
                    refs.setdefault("skill", ref)
                if tool == "load_skill_resource":
                    refs.setdefault("knowledge", ref)
            for category, service in (("kubernetes-mcp", c.kubernetes_service), ("gitlab-mcp", c.gitlab_service)):
                if span.get("service") == service and span.get("toolExecution") == "server":
                    refs.setdefault(category, ref)
            if span.get("component") == "agentgateway" and span.get("kind") == "server" and attrs.get("gen_ai.request.model"):
                refs.setdefault("gateway", ref)
    snapshot = {"schemaVersion": 1, "mode": "live", "observerId": plan["observerId"], "binding": binding,
                "capturedAt": now, "summary": {
                    "fault": "Kyverno's registry-pattern typo rejects the approved application and blocks its Recreate rollout.",
                    "fix": "The native specialist proposed the one-field GitLab repair. Static CI: "
                           + ("passed" if inspection.get("ci_pass") else "pending") + ". Independent review: "
                           + ("passed" if review else "pending") + ". Human approval and live recovery remain pending."},
                "receipts": receipts, "telemetry": refs}
    # This projection intentionally has no approval/merge/recovery receipt.
    return plan, snapshot
