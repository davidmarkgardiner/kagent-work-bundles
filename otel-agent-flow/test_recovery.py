"""Offline receipt/projection tests. Constructed data is not live runtime proof."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import argparse
import sys
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import backend
from recovery import LIMIT, POLICY_OBSERVATION_METHOD, STAGES, project_recovery, read_view
from telemetry import ActivityStore

TRACE = "1" * 32
HEALTHY = "2" * 64
HEAD = "3" * 40
MERGE = "4" * 40
BODY = "5" * 64
NOW = 10000


def valid_documents(now=NOW, mode="live"):
    binding = {"profileRevision": "6" * 64, "incidentId": "incident-demo-1", "runId": "run-demo-1",
               "clusterId": "reviewed-demo-cluster", "namespace": "kyverno-demo", "policyName": "image-policy",
               "ruleName": "trusted-image", "application": "sample-app", "taskId": "native-task-1"}
    plan = {"schemaVersion": 1, "mode": mode, "observerId": "reviewed-observer", "binding": binding,
            "agent": {"namespace": "kagent", "name": "kyverno-specialist"},
            "repository": {"projectId": "demo/policy", "policyPath": "apps/sample/policy.yaml"},
            "reviewerId": "independent-reviewer", "humanApproverId": "reviewed-human",
            "healthyPolicySpecSha256": HEALTHY,
            "application": {"namespace": "kyverno-demo", "deploymentName": "sample-app", "expectedStatus": 200, "expectedBodySha256": BODY},
            "mcpServices": {"kubernetes": "flow-kubernetes-mcp", "gitlab": "flow-gitlab-mcp"}, "maxAgeSeconds": 120}

    def receipt(key, ago, **fields):
        return {"receiptId": "receipt-" + key, "binding": deepcopy(binding), "recordedAt": now - ago, **fields}

    def probe(identifier, ago, kind="valid", result="admitted"):
        return {"probeId": identifier, "observedAt": now - ago, "kind": kind, "result": result}

    receipts = {
        "fault": receipt("fault", 360, policyRevision="7" * 40, policySpecSha256="8" * 64,
                         observations=[probe("fault-" + str(n), ago, result="denied") for n, ago in enumerate((425, 395, 365))],
                         application={"namespace": "kyverno-demo", "deploymentName": "sample-app", "uid": "application-uid",
                                      "observedAt": now - 365, "generation": 2, "observedGeneration": 2,
                                      "desiredReplicas": 1, "updatedReplicas": 0, "availableReplicas": 1}),
        "investigation": receipt("investigation", 350, taskState="accepted"),
        "proposal": receipt("proposal", 340, projectId="demo/policy", mergeRequestIid=17, headSha=HEAD,
                            policyPath="apps/sample/policy.yaml", policySpecSha256=HEALTHY),
        "ci": receipt("ci", 330, headSha=HEAD, pipelineId="pipeline-42", result="passed", validAdmission="admitted", invalidAdmission="denied"),
        "review": receipt("review", 320, headSha=HEAD, reviewerId="independent-reviewer", result="approved"),
        "approval": receipt("approval", 310, headSha=HEAD, approverId="reviewed-human", principalType="human", decision="approved"),
        "merge": receipt("merge", 300, headSha=HEAD, mergeRequestIid=17, mergeSha=MERGE, result="merged"),
        "gitops": receipt("gitops", 200, sourceRevision=MERGE, appliedRevision=MERGE, ready=True),
        "liveObject": receipt("live-object", 90, uid="policy-uid", generation=3, observedGeneration=3,
                              policySpecSha256=HEALTHY, enforcement="Enforce", ready=True, deleting=False),
        "probes": receipt("probes", 5, observedGeneration=3, policySpecSha256=HEALTHY,
                          observations=[probe("valid-" + str(n), ago) for n, ago in enumerate((80, 50, 20))]
                                       + [probe("invalid-1", 10, "invalid", "denied")]),
        "application": receipt("application", 4, namespace="kyverno-demo", deploymentName="sample-app", uid="application-uid",
                               deploymentObservedAt=now - 85, generation=2, observedGeneration=2,
                               desiredReplicas=1, actualReplicas=1, updatedReplicas=1, readyReplicas=1,
                               availableReplicas=1, unavailableReplicas=0,
                               httpObservations=[{"probeId": "http-" + str(n), "observedAt": now - ago,
                                                  "statusCode": 200, "bodySha256": BODY} for n, ago in enumerate((80, 40, 10))]),
        "verification": receipt("verification", 3, taskId="native-task-1", parentTaskId="native-task-1", taskState="completed", result="recovered", mergeSha=MERGE,
                                policySpecSha256=HEALTHY, observedGeneration=3, probeReceiptId="receipt-probes",
                                applicationReceiptId="receipt-application", applicationUid="application-uid", applicationGeneration=2,
                                traceId=TRACE, spanId="0000000000000007"),
    }
    data = {"schemaVersion": 1, "mode": mode, "observerId": plan["observerId"], "binding": deepcopy(binding), "capturedAt": now,
            "summary": {"fault": "Fixture: a policy revision blocks the application's new rollout.",
                        "fix": "Fixture: restore the reviewed image rule through the exact-head MR."},
            "receipts": receipts, "telemetry": {category: {"traceId": TRACE, "spanId": f"{n:016x}"} for n, category in enumerate(
                ("investigation", "model", "skill", "knowledge", "kubernetes-mcp", "gitlab-mcp", "verification", "gateway"), 1)}}
    return plan, data


def active_policy_documents(now=NOW, mode="live"):
    """Constructed missing-status variant; not a live Kyverno receipt."""
    plan, data = valid_documents(now, mode)
    for stage in ("liveObject", "probes", "verification"):
        data["receipts"][stage].update(observedGeneration=None,
                                       observationMethod=POLICY_OBSERVATION_METHOD, activeProbeGeneration=3)
    read = {"uid": "policy-uid", "generation": 3, "policy_spec_sha256": HEALTHY,
            "ready": True, "deleting": False, "enforcement": "Enforce", "observed_at": now - 90}
    data["receipts"]["probes"].update(policyReadBefore=read,
                                         policyReadAfter={**read, "observed_at": now - 6})
    return plan, data


def activity_store(now=NOW, ordinary=False, verification_task=None):
    """Feed actual parser/projector with constructed OTLP. Never a live claim."""
    store = ActivityStore()
    native = {"service.name": "kyverno-specialist", "service.namespace": "kagent"}
    if not ordinary:
        native.update({"kagent.runtime": "adk-go", "gen_ai.main_agent.id": "kagent/kyverno-specialist"})
    common = {"a2a.task.id": "native-task-1", "flow.incident.id": "incident-demo-1", "flow.run.id": "run-demo-1"}

    def attrs(value):
        return [{"key": key, "value": {"stringValue": item}} for key, item in value.items()]

    for n, category in enumerate(("investigation", "model", "skill", "knowledge", "kubernetes-mcp", "gitlab-mcp", "verification", "gateway"), 1):
        values = {**native, **common, "gen_ai.operation.name": "invoke_agent"}
        kind = 1
        if category == "model":
            values.update({"gen_ai.operation.name": "generate_content", "gen_ai.request.model": "fixture-test-model"})
        elif category in {"skill", "knowledge"}:
            tool = ("skills" if category == "skill" else "read_file") if ordinary else ("load_skill" if category == "skill" else "load_skill_resource")
            values.update({"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool})
            if ordinary:
                values["gen_ai.tool.type"] = "SkillsTool" if category == "skill" else "ReadFileTool"
        elif category.endswith("-mcp"):
            values = {**common, "service.name": "flow-kubernetes-mcp" if category == "kubernetes-mcp" else "flow-gitlab-mcp",
                      "mcp.tool.name": "k8s_get_resources" if category == "kubernetes-mcp" else "gitlab_get_latest_pipeline"}
            kind = 2
        elif category == "verification":
            values["a2a.task.state"] = "completed"
            values["a2a.task.id"] = verification_task or "native-task-1"
        elif category == "gateway":
            values = {**common, "service.name": "agentgateway", "gen_ai.request.model": "fixture-test-model"}
            kind = 2
        span = {"traceId": "9" * 32 if category == "verification" and verification_task else TRACE, "spanId": f"{n:016x}", "name": category, "kind": kind,
                "startTimeUnixNano": str((now - 6) * 10**9), "endTimeUnixNano": str((now - 3) * 10**9),
                "status": {"code": 1}, "attributes": attrs(values)}
        environment = {"ORDINARY_AGENT_IDENTITIES": json.dumps([{"namespace": "kagent", "name": "kyverno-specialist"}])} if ordinary else {}
        with patch.dict(os.environ, environment):
            resource = {key: item for key, item in values.items() if key.startswith("service.")}
            store.ingest({"resourceSpans": [{"resource": {"attributes": attrs(resource)}, "scopeSpans": [{"spans": [span]}]}]})
    return store


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.data = valid_documents()
        self.activity = activity_store().snapshot()

    def view(self):
        return project_recovery(self.plan, self.data, self.activity, NOW)

    def test_complete_receipts_and_actual_store_join_reduce_to_recovered(self):
        view = self.view()
        self.assertEqual(view["state"], "recovered", view)
        self.assertTrue(view["completeDemoProof"])
        self.assertEqual(view["expiresAt"], NOW + 30)
        self.assertTrue(all(stage["state"] == "passed" for stage in view["stages"]))

    def test_each_missing_gate_prevents_recovery(self):
        for key, _ in STAGES:
            with self.subTest(stage=key):
                plan, data = valid_documents()
                del data["receipts"][key]
                self.assertNotEqual(project_recovery(plan, data, self.activity, NOW)["state"], "recovered")

    def test_top_level_verified_boolean_and_raw_payload_fields_are_rejected(self):
        for key, value in (("verified", True), ("logs", "secret"), ("prompt", "secret")):
            with self.subTest(key=key):
                self.data[key] = value
                self.assertEqual(self.view()["state"], "unknown")
                del self.data[key]

    def test_head_merge_revision_task_and_target_mismatches_block(self):
        cases = (("review", "headSha", "9" * 40), ("ci", "headSha", "9" * 40),
                 ("approval", "headSha", "9" * 40), ("merge", "headSha", "9" * 40),
                 ("merge", "mergeRequestIid", 99), ("gitops", "sourceRevision", HEAD),
                 ("gitops", "appliedRevision", HEAD), ("verification", "mergeSha", HEAD),
                 ("proposal", "policyPath", "another/policy.yaml"), ("proposal", "projectId", "other-project"),
                 ("approval", "principalType", "agent"), ("approval", "approverId", "other-human"),
                 ("review", "reviewerId", "other-reviewer"), ("verification", "probeReceiptId", "old-probes"))
        for stage, key, value in cases:
            with self.subTest(stage=stage, field=key):
                self.plan, self.data = valid_documents()
                self.data["receipts"][stage][key] = value
                self.assertEqual(self.view()["state"], "blocked")
        for key in self.data["binding"]:
            with self.subTest(binding=key):
                self.plan, self.data = valid_documents()
                self.data["receipts"]["ci"]["binding"][key] = "9" * 64 if key == "profileRevision" else "other"
                self.assertEqual(self.view()["state"], "blocked")

    def test_snapshot_cannot_choose_its_own_profile_observer_or_mode(self):
        for key, value in (("observerId", "unreviewed-observer"), ("mode", "fixture")):
            self.plan, self.data = valid_documents()
            self.data[key] = value
            self.assertEqual(self.view()["state"], "blocked")
        self.data["binding"]["clusterId"] = "another-cluster"
        self.assertEqual(self.view()["state"], "blocked")

    def test_snapshot_stale_and_future_are_unknown(self):
        for offset in (-121, 1):
            self.plan, self.data = valid_documents(NOW + offset)
            self.assertEqual(self.view()["state"], "unknown")

    def test_refreshed_capture_cannot_reuse_old_live_observations(self):
        self.plan, self.data = valid_documents(NOW - 40)
        self.activity = activity_store(NOW - 40).snapshot()
        self.data["capturedAt"] = NOW
        view = self.view()
        self.assertEqual(view["state"], "unknown")
        self.assertIn("stale", " ".join(view["reasons"]))

    def test_future_live_and_probe_observations_do_not_recover(self):
        self.data["receipts"]["liveObject"]["recordedAt"] = NOW + 1
        self.assertNotEqual(self.view()["state"], "recovered")
        self.plan, self.data = valid_documents()
        self.data["receipts"]["probes"]["observations"][-1]["observedAt"] = NOW + 1
        self.assertEqual(self.view()["state"], "unknown")

    def test_policy_generation_body_enforcement_and_delete_checks(self):
        for key, value in (("observedGeneration", 2), ("policySpecSha256", "9" * 64),
                           ("enforcement", "Audit"), ("deleting", True), ("ready", False)):
            self.plan, self.data = valid_documents()
            self.data["receipts"]["liveObject"][key] = value
            self.assertEqual(self.view()["state"], "blocked")

    def test_active_policy_proof_keeps_native_generation_null(self):
        self.plan, self.data = active_policy_documents()
        before = deepcopy(self.data)
        view = self.view()
        self.assertEqual(view["state"], "recovered", view)
        self.assertTrue(view["completeDemoProof"])
        self.assertEqual(self.data, before)
        self.assertTrue(all(self.data["receipts"][stage]["observedGeneration"] is None
                            for stage in ("liveObject", "probes", "verification")))

    def test_null_policy_status_requires_explicit_consistent_proof_at_each_stage(self):
        for stage in ("liveObject", "probes", "verification"):
            for field, value in (("observationMethod", "unknown"), ("activeProbeGeneration", 2),
                                 ("observedGeneration", 3)):
                with self.subTest(stage=stage, field=field):
                    self.plan, self.data = active_policy_documents()
                    self.data["receipts"][stage][field] = value
                    self.assertNotEqual(self.view()["state"], "recovered")
            for field in ("observationMethod", "activeProbeGeneration"):
                self.plan, self.data = active_policy_documents()
                del self.data["receipts"][stage][field]
                self.assertNotEqual(self.view()["state"], "recovered")
        self.plan, self.data = valid_documents()
        for stage in ("liveObject", "probes", "verification"):
            self.data["receipts"][stage]["observedGeneration"] = None
        self.assertEqual(self.view()["state"], "blocked")

    def test_active_proof_cannot_override_mismatching_present_native_status(self):
        for generation in (2, 3):
            self.plan, self.data = active_policy_documents()
            for stage in ("liveObject", "probes", "verification"):
                self.data["receipts"][stage]["observedGeneration"] = generation
            self.assertEqual(self.view()["state"], "blocked")

    def test_active_policy_reads_require_exact_identity_ready_enforce_and_no_deletion(self):
        for side in ("policyReadBefore", "policyReadAfter"):
            for field, value in (("uid", "replaced-policy"), ("generation", 4),
                                 ("policy_spec_sha256", "9" * 64), ("ready", False),
                                 ("enforcement", "Audit"), ("deleting", True)):
                with self.subTest(side=side, field=field):
                    self.plan, self.data = active_policy_documents()
                    self.data["receipts"]["probes"][side][field] = value
                    self.assertEqual(self.view()["state"], "blocked")
            self.plan, self.data = active_policy_documents()
            del self.data["receipts"]["probes"][side]
            self.assertEqual(self.view()["state"], "blocked")

    def test_active_policy_reads_must_bracket_all_actual_admission_probes(self):
        cases = (("policyReadBefore", NOW - 79), ("policyReadAfter", NOW - 11),
                 ("policyReadAfter", NOW - 4))
        for side, observed_at in cases:
            self.plan, self.data = active_policy_documents()
            self.data["receipts"]["probes"][side]["observed_at"] = observed_at
            self.assertEqual(self.view()["state"], "blocked")
        for side, observed_at in (("policyReadBefore", NOW - 121), ("policyReadAfter", NOW + 1)):
            self.plan, self.data = active_policy_documents()
            self.data["receipts"]["probes"][side]["observed_at"] = observed_at
            self.assertEqual(self.view()["state"], "unknown")

    def test_active_policy_read_shape_stays_metadata_only_and_typed(self):
        for field, value in (("headers", {"Authorization": "private"}), ("ready", 1),
                             ("deleting", 0), ("generation", True), ("observed_at", 1.5)):
            self.plan, self.data = active_policy_documents()
            self.data["receipts"]["probes"]["policyReadBefore"][field] = value
            self.assertEqual(self.view()["state"], "unknown")
        self.plan, self.data = active_policy_documents()
        self.data["receipts"]["application"]["observedGeneration"] = None
        self.assertEqual(self.view()["state"], "unknown")

    def test_active_policy_proof_retains_admission_and_native_telemetry_requirements(self):
        for kind, result in (("valid", "denied"), ("invalid", "admitted"), ("valid", "error")):
            self.plan, self.data = active_policy_documents()
            self.data["receipts"]["probes"]["observations"].append(
                {"probeId": "later-failure", "observedAt": NOW - 7, "kind": kind, "result": result})
            self.assertEqual(self.view()["state"], "blocked")
        self.plan, self.data = active_policy_documents()
        self.assertEqual(project_recovery(self.plan, self.data, {}, NOW)["state"], "unknown")
        self.activity["traces"][0]["spans"][6]["attributes"]["flow.simulated"] = True
        self.assertEqual(self.view()["state"], "unknown")
        self.plan, self.data = active_policy_documents(mode="fixture")
        view = project_recovery(self.plan, self.data, {}, NOW)
        self.assertEqual(view["state"], "replay-passed")
        self.assertFalse(view["completeDemoProof"])

    def test_each_later_bad_probe_removes_green_and_duplicate_probes_do_not_count(self):
        for kind, result in (("valid", "denied"), ("invalid", "admitted"), ("valid", "error")):
            self.plan, self.data = valid_documents()
            self.data["receipts"]["probes"]["observations"].append(
                {"probeId": "later-failure", "observedAt": NOW - 6, "kind": kind, "result": result})
            self.assertEqual(self.view()["state"], "blocked")
        self.plan, self.data = valid_documents()
        probes = self.data["receipts"]["probes"]["observations"]
        probes[1]["probeId"] = probes[0]["probeId"]
        self.assertEqual(self.view()["state"], "unknown")

    def test_missing_enforcement_denial_or_short_probe_window_blocks(self):
        self.data["receipts"]["probes"]["observations"].pop()
        self.assertEqual(self.view()["state"], "blocked")
        self.plan, self.data = valid_documents()
        self.data["receipts"]["probes"]["observations"][0]["observedAt"] = NOW - 70
        self.assertEqual(self.view()["state"], "blocked")

    def test_application_must_finish_current_rollout_even_if_old_replica_serves(self):
        for key, value in (("updatedReplicas", 0), ("actualReplicas", 2), ("availableReplicas", 0),
                           ("readyReplicas", 0), ("unavailableReplicas", 1), ("observedGeneration", 1),
                           ("desiredReplicas", 0), ("uid", "replacement-uid"), ("deploymentName", "other-app")):
            with self.subTest(field=key):
                self.plan, self.data = valid_documents()
                self.data["receipts"]["application"][key] = value
                self.assertNotEqual(self.view()["state"], "recovered")

    def test_application_response_digest_status_and_later_failure_block(self):
        for key, value in (("statusCode", 503), ("bodySha256", "9" * 64)):
            self.plan, self.data = valid_documents()
            self.data["receipts"]["application"]["httpObservations"][-1][key] = value
            self.assertEqual(self.view()["state"], "blocked")
        self.data["receipts"]["application"]["httpObservations"].append(
            {"probeId": "http-later-failure", "observedAt": NOW - 5, "statusCode": 503, "bodySha256": BODY})
        self.assertEqual(self.view()["state"], "blocked")

    def test_application_recovery_needs_repeated_http_reads_and_native_binding(self):
        self.data["receipts"]["application"]["httpObservations"] = self.data["receipts"]["application"]["httpObservations"][-1:]
        self.assertEqual(self.view()["state"], "blocked")
        for key, value in (("applicationReceiptId", "another-receipt"), ("applicationUid", "other-uid"), ("applicationGeneration", 1)):
            self.plan, self.data = valid_documents()
            self.data["receipts"]["verification"][key] = value
            self.assertEqual(self.view()["state"], "blocked")

    def test_fault_requires_a_real_blocked_application_rollout(self):
        self.data["receipts"]["fault"]["application"]["updatedReplicas"] = 1
        self.assertEqual(self.view()["state"], "blocked")

    def test_fixture_receipts_can_only_show_fixture_replay(self):
        self.plan, self.data = valid_documents(mode="fixture")
        view = project_recovery(self.plan, self.data, {}, NOW)
        self.assertEqual(view["state"], "replay-passed")
        self.assertEqual(view["label"], "Fixture replay passed")
        self.assertFalse(view["completeDemoProof"])
        self.assertEqual(view["telemetry"]["state"], "incomplete")

    def test_missing_telemetry_is_unknown_without_inventing_activity(self):
        self.assertEqual(project_recovery(self.plan, self.data, {}, NOW)["state"], "unknown")
        self.data["telemetry"].pop("knowledge")
        view = self.view()
        self.assertEqual(view["state"], "recovered")
        self.assertFalse(view["completeDemoProof"])
        self.assertEqual(next(c for c in view["telemetry"]["checks"] if c["category"] == "knowledge")["state"], "unknown")

    def test_wrong_trace_span_task_and_incident_cannot_correlate(self):
        for key, value in (("traceId", "9" * 32), ("spanId", "9" * 16)):
            self.plan, self.data = valid_documents()
            self.data["telemetry"]["verification"][key] = value
            self.assertEqual(self.view()["state"], "unknown")
        for key in ("a2a.task.id", "flow.incident.id", "flow.run.id"):
            self.plan, self.data = valid_documents()
            self.activity = activity_store().snapshot()
            self.activity["traces"][0]["spans"][6]["attributes"][key] = "wrong"
            self.assertEqual(self.view()["state"], "unknown")

    def test_old_or_contradictory_native_verification_cannot_recover(self):
        self.activity["traces"][0]["spans"][6]["endNs"] = str((NOW - 20) * 10**9)
        self.assertEqual(self.view()["state"], "blocked")
        self.activity = activity_store().snapshot()
        self.activity["traces"][0]["spans"][6]["attributes"]["a2a.task.state"] = "failed"
        self.assertEqual(self.view()["state"], "blocked")

    def test_follow_up_verification_requires_exact_reviewed_task_and_parent(self):
        self.plan["verificationTaskId"] = "reviewed-follow-up-task"
        receipt = self.data["receipts"]["verification"]
        receipt["taskId"] = "reviewed-follow-up-task"
        receipt["traceId"] = "9" * 32
        self.data["telemetry"]["verification"]["traceId"] = "9" * 32
        self.activity = activity_store(verification_task="reviewed-follow-up-task").snapshot()
        view = self.view()
        self.assertEqual(view["state"], "recovered", view)
        self.assertTrue(view["completeDemoProof"])
        receipt["parentTaskId"] = "unrelated-parent"
        self.assertEqual(self.view()["state"], "blocked")
        receipt["parentTaskId"] = "native-task-1"
        del self.plan["verificationTaskId"]
        self.assertEqual(self.view()["state"], "blocked")
        self.plan["verificationTaskId"] = "reviewed-follow-up-task"
        self.activity = activity_store(verification_task="unreviewed-follow-up-task").snapshot()
        self.assertEqual(self.view()["state"], "unknown")

    def test_simulated_verification_span_is_not_live_proof(self):
        self.activity["traces"][0]["spans"][6]["attributes"]["flow.simulated"] = True
        self.assertEqual(self.view()["state"], "unknown")

    def test_ordinary_native_skill_names_have_real_parser_support(self):
        identities = [{"namespace": "kagent", "name": "kyverno-specialist"}]
        with patch.dict(os.environ, {"ORDINARY_AGENT_IDENTITIES": json.dumps(identities)}):
            view = project_recovery(self.plan, self.data, activity_store(ordinary=True).snapshot(), NOW)
        self.assertTrue(view["completeDemoProof"], view)

    def test_refs_must_describe_actual_operation_kind_and_pinned_mcp_service(self):
        self.data["telemetry"]["knowledge"] = self.data["telemetry"]["model"]
        self.activity["traces"][0]["spans"][4]["service"] = "unreviewed-mcp"
        view = self.view()
        self.assertEqual(view["state"], "recovered")
        self.assertFalse(view["completeDemoProof"])

    def test_hashes_ids_boolean_counters_and_unexpected_fields_are_strict(self):
        for stage, key, value in (("merge", "mergeSha", "short"), ("ci", "headSha", "a" * 41),
                                  ("approval", "verified", True), ("application", "desiredReplicas", True),
                                  ("liveObject", "ready", 1)):
            self.plan, self.data = valid_documents()
            self.data["receipts"][stage][key] = value
            self.assertEqual(self.view()["state"], "unknown")

    def test_mounted_reads_are_optional_bounded_and_reject_duplicate_keys(self):
        self.assertFalse(read_view()["enabled"])
        self.assertEqual(read_view("/missing", None)["state"], "unknown")
        with tempfile.TemporaryDirectory() as directory:
            plan, data = Path(directory) / "profile.json", Path(directory) / "recovery.json"
            plan.write_text(json.dumps(self.plan))
            data.write_text(json.dumps(self.data))
            self.assertEqual(read_view(data, plan, self.activity, NOW)["state"], "recovered")
            for content in (b"x" * (LIMIT + 1), b'{"schemaVersion":1,"schemaVersion":1}', b"{", b'NaN'):
                data.write_bytes(content)
                self.assertEqual(read_view(data, plan, self.activity, NOW)["state"], "unknown")
            data.unlink()
            self.assertEqual(read_view(data, plan, self.activity, NOW)["state"], "unknown")

    def test_trace_and_log_correlation_keep_only_allowed_metadata(self):
        store = activity_store()
        attributes = [{"key": key, "value": {"stringValue": value}} for key, value in {
            "flow.incident.id": "incident-demo-1", "flow.run.id": "run-demo-1", "gen_ai.task.id": "native-task-1",
            "prompt": "private-prompt", "secret": "private-secret"}.items()]
        store.ingest_logs({"resourceLogs": [{"scopeLogs": [{"logRecords": [{"timeUnixNano": str(NOW * 10**9),
            "traceId": TRACE, "spanId": "0000000000000007", "attributes": attributes,
            "body": {"stringValue": "private-log-body"}}]}]}]})
        logs = store.logs_snapshot(TRACE)
        self.assertEqual(logs["logs"][0]["attributes"]["flow.incident.id"], "incident-demo-1")
        self.assertEqual(logs["logs"][0]["attributes"]["gen_ai.task.id"], "native-task-1")
        self.assertNotIn("private-", json.dumps(logs))
        self.assertEqual(store.snapshot()["traces"][0]["spans"][0]["attributes"]["flow.run.id"], "run-demo-1")


class RecoveryHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), backend.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_real_state_endpoint_reports_profile_snapshot_and_imported_module(self):
        now = int(time.time())
        profile, snapshot = valid_documents(now)
        with tempfile.TemporaryDirectory() as directory:
            plan, data = Path(directory) / "profile.json", Path(directory) / "snapshot.json"
            plan.write_text(json.dumps(profile))
            data.write_text(json.dumps(snapshot))
            with patch.dict(os.environ, {"READ_ONLY_VIEWER": "true", "RECOVERY_PROFILE": str(plan), "RECOVERY_SNAPSHOT": str(data)}), patch("backend.STORE", activity_store(now)):
                with urllib.request.urlopen(self.url + "/api/state", timeout=5) as response:
                    view = json.load(response)
                self.assertEqual(view["recovery"]["state"], "recovered")
                self.assertTrue(view["recovery"]["completeDemoProof"])
                data.write_text("{}")
                with urllib.request.urlopen(self.url + "/api/state", timeout=5) as response:
                    self.assertEqual(json.load(response)["recovery"]["state"], "unknown")

    def test_no_recovery_write_endpoint_is_introduced(self):
        request = urllib.request.Request(self.url + "/api/recovery", b"{}", {"Content-Type": "application/json"})
        with urllib.request.urlopen(self.url + "/api/state", timeout=5) as response:
            self.assertIn("recovery", json.load(response))
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 404)


def write_fixture(directory):
    """Export labelled receipt fixtures only, without creating any OTel spans."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plan, snapshot = valid_documents(int(time.time()), mode="fixture")
    plan["maxAgeSeconds"] = 300
    for name, value in (("profile", plan), ("snapshot", snapshot)):
        target = directory / ("recovery-fixture-" + name + ".json")
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        print(target)


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        parser = argparse.ArgumentParser(description="Export fixture replay receipts, never live runtime proof")
        parser.add_argument("--write-fixture", type=Path, required=True)
        write_fixture(parser.parse_args().write_fixture)
    else:
        unittest.main()
