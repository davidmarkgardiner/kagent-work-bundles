"""Offline tests: fakes establish logic only, never live API/model proof."""
import base64
import copy
from dataclasses import replace
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from urllib.parse import parse_qs, unquote, urlsplit

from admission import Admission, MAX_CLASSIFICATIONS, VALID_IMAGE
from core import (APIError, CAUSE, FAULTY_PATTERN, HEALTHY_PATTERN, POLICY_OBSERVATION_METHOD,
                  Config, HTTPJSON, Ledger, Rejected, Telemetry, TraceContext, canonical, digest)
from runtime import Handler, Runtime, TOOLS, policy_read_metadata

BASE, HEAD, MERGE = "a" * 40, "b" * 40, "c" * 40
NOW = 1700000200


def policies():
    faulty = {"apiVersion": "kyverno.io/v1", "kind": "Policy", "metadata": {"name": "approved-registry", "namespace": "kyverno-recovery-demo",
              "annotations": {"pod-policies.kyverno.io/autogen-controllers": "none"}},
              "spec": {"background": False, "rules": [{"name": "approved-registry", "match": {"any": [{"resources": {"kinds": ["Pod"],
                       "selector": {"matchLabels": {"app.kubernetes.io/name": "registry-demo"}}}}]},
                       "validate": {"failureAction": "Enforce", "message": "Approved images only", "pattern": {"spec": {"containers": [{"image": FAULTY_PATTERN}]}}}}]}}
    healthy = copy.deepcopy(faulty)
    healthy["spec"]["rules"][0]["validate"]["pattern"]["spec"]["containers"][0]["image"] = HEALTHY_PATTERN
    return faulty, healthy


def config():
    faulty, healthy = policies()
    v = json.loads(Path(__file__).with_name("config.example.json").read_text())
    v.update({"faulty_policy_sha256": digest(faulty), "faulty_policy_spec_sha256": digest(faulty["spec"]),
              "healthy_policy_sha256": digest(healthy), "healthy_policy_spec_sha256": digest(healthy["spec"]),
              "expected_body_sha256": hashlib.sha256(b"recovered\n").hexdigest(), "otlp_endpoint": ""})
    return Config.from_dict(v)


class FakeGitLab:
    def __init__(self, cfg, ledger):
        self.cfg, self.ledger = cfg, ledger
        self.faulty, self.healthy = policies()
        self.branches = {cfg.target_branch: BASE}
        self.docs = {BASE: self.faulty, HEAD: self.healthy, MERGE: self.healthy}
        self.writes = []
        self.timeout = None
        self.mr = None
        self.pipeline_status = "success"
        self.missing_test = False
        self.missing_report = False
        self.diff_extra = False

    def request(self, path, method="GET", body=None, traceparent=None):
        prefix = "/projects/" + self.cfg.project_id
        assert path.startswith(prefix)
        parsed = urlsplit(path[len(prefix):])
        p, q = parsed.path, parse_qs(parsed.query)
        if method != "GET":
            expected_op = {"/repository/commits": "policy-fix-commit", "/merge_requests": "policy-fix-mr", "/merge_requests/1/merge": "policy-fix-merge" if self.ledger.operation("policy-fix-merge") else "flow-dashboard-merge"}[p]
            assert self.ledger.operation(expected_op)["status"] == "unknown", "intent must persist before mutation"
            self.writes.append((p, copy.deepcopy(body)))
            if self.timeout == "before:" + p:
                raise APIError("fake")
            if p == "/repository/commits":
                assert body["start_sha"] == BASE
                assert 'last_commit_id' not in body['actions'][0]
                assert self.cfg.fix_branch not in self.branches
                self.branches[self.cfg.fix_branch] = HEAD
                result = {"id": HEAD}
            elif p == "/merge_requests":
                self.mr = {"iid": 1, "sha": HEAD, "source_branch": self.cfg.fix_branch, "target_branch": self.cfg.target_branch,
                           "source_project_id": int(self.cfg.project_id), "target_project_id": int(self.cfg.project_id),
                           "web_url": "https://gitlab.example.invalid/demo/-/merge_requests/1", "state": "opened", "draft": False,
                           "detailed_merge_status": "mergeable", "merge_commit_sha": None}
                result = copy.deepcopy(self.mr)
            else:
                assert body["sha"] == HEAD
                self.mr.update({"state": "merged", "merge_commit_sha": MERGE, "merged_at": "2023-11-14T22:16:40Z"})
                self.branches[self.cfg.target_branch] = MERGE
                result = copy.deepcopy(self.mr)
            if self.timeout == "after:" + p:
                raise APIError("fake")
            return result
        if p.startswith("/repository/branches/"):
            name = unquote(p.split("/repository/branches/", 1)[1])
            if name not in self.branches:
                raise APIError("fake", 404)
            return {"name": name, "commit": {"id": self.branches[name]}}
        if p.startswith("/repository/files/"):
            ref = q["ref"][0]
            ref = self.branches.get(ref, ref)
            return {"file_path": self.cfg.policy_file, "encoding": "base64", "content": base64.b64encode(canonical(self.docs[ref])).decode(), "last_commit_id": ref}
        if p == "/repository/commits/" + HEAD:
            return {"id": HEAD, "parent_ids": [BASE], "title": "Repair approved registry [" + self.cfg.run_id + "]"}
        if p.endswith("/diff") or p.endswith("/diffs"):
            result = [{"old_path": self.cfg.policy_file, "new_path": self.cfg.policy_file, "diff": "-docker.io/libary/*\n+docker.io/library/*\n"}]
            if self.diff_extra:
                result.append({"old_path": "other.json", "new_path": "other.json", "diff": "bad"})
            return result
        if p == "/merge_requests":
            return [copy.deepcopy(self.mr)] if self.mr else []
        if p == "/merge_requests/1":
            return copy.deepcopy(self.mr)
        if p == "/pipelines":
            return [{"id": 7, "sha": HEAD, "status": self.pipeline_status}]
        if p == "/pipelines/7":
            return {"id": 7, "sha": HEAD, "status": self.pipeline_status, "ref": self.cfg.fix_branch}
        if p == "/pipelines/7/jobs":
            return [{"id": 9, "name": "policy-tests", "status": "success"}]
        if p == "/pipelines/7/test_report":
            if self.missing_report:
                raise APIError("fake", 404)
            return {"test_suites": [{"test_cases": [{"name": name, "status": "failed" if self.missing_test and name.startswith("invalid") else "success"}
                                                       for name in self.cfg.required_test_cases]}]}
        raise AssertionError((method, path))


class FakeKube:
    def __init__(self, cfg):
        self.cfg = cfg
        self.policy = copy.deepcopy(policies()[1])
        self.policy["metadata"].update({"uid": "policy-uid", "generation": 3})
        self.policy["status"] = {"ready": True, "observedGeneration": 3}
        self.calls = []
        self.change_policy_on_second = False
        self.policy_reads = 0

    def request(self, path, method="GET", body=None, traceparent=None):
        assert method == "GET" and body is None
        self.calls.append(path)
        if "/policies/" in path:
            self.policy_reads += 1
            value = copy.deepcopy(self.policy)
            if self.change_policy_on_second and self.policy_reads >= 2:
                value["metadata"]["generation"] += 1
            return value
        if "/deployments/" in path:
            return {"metadata": {"uid": "deployment-uid", "generation": 3}, "spec": {"replicas": 1, "strategy": {"type": "Recreate"},
                    "template": {"spec": {"containers": [{"image": VALID_IMAGE}]}}},
                    "status": {"observedGeneration": 3, "replicas": 1, "updatedReplicas": 1, "readyReplicas": 1, "availableReplicas": 1}}
        if "/replicasets?" in path:
            return {"items": [{"metadata": {"uid": "rs-uid", "name": "registry-demo-123", "ownerReferences": [{"uid": "deployment-uid", "kind": "Deployment"}]}, "status": {"replicas": 0}}]}
        if "/pods?" in path:
            return {"items": []}
        if "/events?" in path:
            return {"items": [{"metadata": {"uid": "event-uid"}, "reason": "FailedCreate", "message": "approved-registry denied rule approved-registry",
                               "involvedObject": {"uid": "rs-uid"}}]}
        return {"metadata": {"generation": 1}, "status": {"observedGeneration": 1, "artifact": {"revision": "main@sha1:" + MERGE},
                    "lastAppliedRevision": "main@sha1:" + MERGE, "conditions": [{"type": "Ready", "status": "True"}]}}


class FakeTelemetry:
    def __init__(self):
        self.calls = []

    def export(self, *args):
        self.calls.append(args)


def observation(cfg, index=0, when=None, native=True):
    when = NOW - 90 + index * 30 if when is None else when
    policy = {"uid": "faulty-policy-uid", "generation": 2, "observed_generation": 2 if native else None,
              "policy_spec_sha256": cfg.faulty_policy_spec_sha256, "policy_revision": BASE, "image_pattern": FAULTY_PATTERN}
    if not native:
        metadata = {"uid": policy["uid"], "generation": 2, "policy_spec_sha256": cfg.faulty_policy_spec_sha256,
                    "ready": True, "deleting": False, "enforcement": "Enforce", "observed_at": when}
        policy.update({"observation_method": POLICY_OBSERVATION_METHOD, "policy_read_before": metadata, "policy_read_after": dict(metadata)})
    return {"schema_version": 1, **{key: getattr(cfg, key) for key in ("cluster_id", "namespace", "application", "policy_name", "rule_name")},
            "cause": CAUSE, "probe": {"probe_id": "probe-" + str(index), "observed_at": when, "kind": "valid", "result": "denied", "image": VALID_IMAGE},
            "policy": policy, "denial": {"source": "kubernetes-dry-run", "policy_name": cfg.policy_name, "rule_name": cfg.rule_name},
            "rollout": {"uid": "deployment-uid", "generation": 2, "observed_generation": 2, "desired_replicas": 1, "updated_replicas": 0, "available_replicas": 0,
                        "failed_create": True, "event_id": "event-" + str(index), "policy_name": cfg.policy_name, "rule_name": cfg.rule_name}}


def classification(packet, _limits, choice="investigate", confidence=0.99, request_id="classifier-request-1"):
    return {"request_id": request_id, "model": "fake-offline", "usage": {"input_tokens": 800, "output_tokens": 100},
            "result": {"choice": choice, "severity": "critical", "confidence": confidence, "cause": CAUSE, "evidence_ids": packet["evidence_ids"]}}


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = config()
        self.db_path = Path(self.temp.name) / "state.sqlite"
        self.ledger = Ledger(self.db_path, self.cfg.identity)
        self.addCleanup(self.ledger.close)
        self.gl = FakeGitLab(self.cfg, self.ledger)
        self.kube = FakeKube(self.cfg)
        self.telemetry = FakeTelemetry()
        self.rt = Runtime(self.cfg, self.ledger, self.gl, self.kube, self.telemetry, now=lambda: NOW)
        self.ad = Admission(self.cfg, self.ledger, now=lambda: NOW)

    def candidate(self, native=True, start=0):
        for i in range(start, start + 3):
            outcome = self.ad.observe(observation(self.cfg, i, NOW - 90 + (i - start) * 30, native))
        self.assertEqual(outcome["state"], "candidate")
        return outcome["candidate_id"]

    def native_task(self):
        candidate_id = self.candidate()
        self.assertEqual(self.ad.classify(candidate_id, classification)["state"], "accepted")
        self.ad.dispatch(lambda packet: {"message_id": packet["message_id"], "task_id": "native-specialist-task", "task_state": "WORKING"})

    def proposal(self):
        result = self.rt.propose_policy_fix("Three exact policy denials and blocked rollout demonstrate this registry typo.", HEALTHY_PATTERN)
        self.assertTrue(result["diff_valid"])
        return result["binding"]

    def review(self, binding):
        self.rt.control({"action": "record_review", "binding": binding, "reviewer_id": self.cfg.reviewer_id,
                         "task_id": "native-reviewer-task", "task_state": "COMPLETED", "verdict": "PASS",
                         "native_receipt_sha256": "1" * 64, "reviewed_at": NOW, "valid_admission": "pass", "invalid_admission": "pass"})

    def authorize(self, binding):
        self.native_task()
        self.review(binding)
        self.rt.control({"action": "record_native_approval_request", "binding": binding, "task_id": "native-specialist-task",
                         "approval_id": "native-approval-1", "tool_call_id": "native-call-1", "tool_name": "merge_policy_fix",
                         "task_state": "INPUT_REQUIRED", "native_receipt_sha256": "2" * 64, "observed_at": NOW})
        return self.rt.control({"action": "authorize_merge", "binding": binding, "task_id": "native-specialist-task",
                         "approval_id": "native-approval-1", "tool_call_id": "native-call-1", "tool_name": "merge_policy_fix",
                         "decision": "approved", "principal_type": "human", "principal_id": self.cfg.human_approver_id,
                         "native_receipt_sha256": "3" * 64, "decided_at": NOW})


class AdmissionTests(BaseTest):
    def test_three_distinct_denials_and_window(self):
        self.ad.observe(observation(self.cfg, 0))
        self.assertEqual(self.ad.observe(observation(self.cfg, 0))["state"], "replay")
        self.assertEqual(self.ad.observe(observation(self.cfg, 1))["state"], "observing")
        self.assertEqual(self.ad.observe(observation(self.cfg, 2))["state"], "candidate")

    def test_short_and_too_long_windows_do_not_admit(self):
        for i, at in enumerate([NOW - 150, NOW - 20, NOW - 5]):
            self.assertEqual(self.ad.observe(observation(self.cfg, i, at))["state"], "observing")

    def test_normal_enforcement_scope_and_corrob_suppressed(self):
        for key in ("invalid", "scope", "rollout", "policy", "specific", "stale"):
            p = observation(self.cfg)
            if key == "invalid": p["probe"]["kind"] = "invalid"
            if key == "scope": p["namespace"] = "other"
            if key == "rollout": p["rollout"]["available_replicas"] = 1
            if key == "policy": p["policy"]["policy_spec_sha256"] = "d" * 64
            if key == "specific": p["denial"]["rule_name"] = "other"
            if key == "stale": p["probe"]["observed_at"] = NOW - 1000
            self.assertEqual(self.ad.observe(p)["state"], "suppressed")

    def test_reused_probe_identity_cannot_change_evidence(self):
        p = observation(self.cfg)
        self.ad.observe(p)
        p["probe"]["observed_at"] += 1
        with self.assertRaises(Rejected): self.ad.observe(p)

    def test_fingerprint_survives_run_and_revision_changes(self):
        newer = replace(self.cfg, run_id="new-run", profile_revision="e" * 64)
        self.assertEqual(self.cfg.fingerprint, newer.fingerprint)
        self.assertNotEqual(self.cfg.identity, newer.identity)

    def test_missing_native_generation_requires_explicit_bracket(self):
        p = observation(self.cfg, native=False)
        del p["policy"]["policy_read_after"]
        self.assertEqual(self.ad.observe(p)["state"], "suppressed")
        self.candidate(native=False)

    def test_model_budget_reserved_before_callback_and_replay(self):
        candidate_id = self.candidate()
        calls = []
        def callback(packet, limits):
            calls.append(packet)
            self.assertEqual(self.ad.state()["classifier_requests_reserved"], 1)
            self.assertEqual(limits["max_output_tokens"], 512)
            return classification(packet, limits)
        self.assertEqual(self.ad.classify(candidate_id, callback)["state"], "accepted")
        self.assertEqual(self.ad.classify(candidate_id, callback)["state"], "accepted")
        self.assertEqual(len(calls), 1)

    def test_outage_consumes_allowance_and_restart_no_retry(self):
        candidate_id = self.candidate()
        def unavailable(*_args): raise TimeoutError()
        self.assertEqual(self.ad.classify(candidate_id, unavailable)["state"], "unknown")
        restarted = Admission(self.cfg, self.db_path, now=lambda: NOW)
        self.addCleanup(restarted.ledger.close)
        self.assertEqual(restarted.classify(candidate_id, lambda *_: self.fail("must not retry"))["state"], "unknown")
        self.assertEqual(restarted.state()["classifier_requests_reserved"], 1)

    def test_budget_twelve_survives_restart(self):
        candidate_id = self.candidate()
        packet = self.ad.candidate(candidate_id).packet
        for i in range(MAX_CLASSIFICATIONS):
            changed = copy.deepcopy(packet)
            changed["candidate_id"] = digest(["candidate", i])
            cid = changed["candidate_id"]
            with self.ledger.transaction() as db:
                db.execute("INSERT OR IGNORE INTO candidates VALUES(?,?,?)", (cid, canonical(changed).decode(), NOW))
            self.ad.classify(cid, lambda p, l: classification(p, l, choice="ignore", request_id="request-" + str(i)))
        with self.assertRaises(Rejected): self.ad.classify(candidate_id, classification)
        self.assertEqual(self.ad.state()["classifier_requests_reserved"], 12)

    def test_wrong_evidence_and_low_confidence_cannot_dispatch(self):
        cid = self.candidate()
        def wrong(packet, limits):
            value = classification(packet, limits)
            value["result"]["evidence_ids"] = ["invented"]
            return value
        self.assertEqual(self.ad.classify(cid, wrong)["state"], "unknown")
        with self.assertRaises(Rejected): self.ad.dispatch(lambda _: self.fail("no dispatch"))

    def test_low_confidence_suppresses(self):
        cid = self.candidate()
        self.assertEqual(self.ad.classify(cid, lambda p, l: classification(p, l, confidence=0.94))["state"], "suppressed")
        with self.assertRaises(Rejected): self.ad.dispatch(lambda _: self.fail("no dispatch"))

    def test_unknown_dispatch_no_retry_and_original_id_reconciliation(self):
        cid = self.candidate()
        self.ad.classify(cid, classification)
        captured = []
        def timeout(packet):
            captured.append(packet)
            self.assertEqual(self.ad.state()["outbox"]["status"], "unknown")
            raise TimeoutError()
        result = self.ad.dispatch(timeout)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(self.ad.dispatch(lambda _: self.fail("no retry"))["state"], "unknown")
        with self.assertRaises(Rejected): self.ad.reconcile_dispatch({"message_id": "other", "task_id": "task", "task_state": "WORKING"})
        receipt = {"message_id": result["message_id"], "task_id": "actual-native-task", "task_state": "WORKING"}
        self.assertEqual(self.ad.reconcile_dispatch(receipt)["state"], "accepted")
        self.assertEqual(self.ad.dispatch(lambda _: self.fail("no duplicate"))["task_id"], "actual-native-task")

    def test_database_cannot_rebind_another_run(self):
        with self.assertRaises(Rejected): Ledger(self.db_path, replace(self.cfg, run_id="other").identity)

    def test_mixed_policy_generations_cannot_form_candidate(self):
        self.ad.observe(observation(self.cfg, 0))
        self.ad.observe(observation(self.cfg, 1))
        p = observation(self.cfg, 2)
        p["policy"].update({"generation": 3, "observed_generation": 3})
        self.assertEqual(self.ad.observe(p)["state"], "observing")

    def test_stale_candidate_does_not_spend_or_dispatch(self):
        cid = self.candidate()
        stale = Admission(self.cfg, self.ledger, now=lambda: NOW + 1000)
        with self.assertRaises(Rejected): stale.classify(cid, lambda *_: self.fail("stale evidence must not invoke model"))
        self.assertEqual(stale.state()["classifier_requests_reserved"], 0)
        self.ad.classify(cid, classification)
        with self.assertRaises(Rejected): stale.dispatch(lambda _: self.fail("stale evidence must not create task"))

    def test_output_allowance_and_reused_model_request_id(self):
        cid = self.candidate()
        self.ad.classify(cid, classification)
        packet = copy.deepcopy(self.ad.candidate(cid).packet)
        packet["candidate_id"] = digest(["new", cid])
        with self.ledger.transaction() as db:
            db.execute("INSERT INTO candidates VALUES(?,?,?)", (packet["candidate_id"], canonical(packet).decode(), NOW))
        self.assertEqual(self.ad.classify(packet["candidate_id"], classification)["reason"], "classifier_request_id_reused")
        self.assertEqual(self.ad.state()["classifier_requests_reserved"], 2)

    def test_crash_pending_outbox_becomes_unknown_without_delivery(self):
        with self.ledger.transaction() as db:
            value = {"message_id": "original-message", "run_id": self.cfg.run_id}
            db.execute("INSERT INTO outbox VALUES(1,?,'pending',?)", (value["message_id"], canonical(value).decode()))
        self.assertEqual(self.ad.dispatch(lambda _: self.fail("pending identity cannot be blindly resent"))["state"], "unknown")


class RuntimeTests(BaseTest):
    def test_proposal_exact_field_and_idempotency(self):
        binding = self.proposal()
        self.assertEqual(binding["head_sha"], HEAD)
        self.proposal()
        self.assertEqual(len(self.gl.writes), 2)
        contents = json.loads(self.gl.writes[0][1]["actions"][0]["content"])
        self.assertEqual(contents, policies()[1])

    def test_reject_arbitrary_patterns_and_unknown_file(self):
        with self.assertRaises(Rejected): self.rt.propose_policy_fix("Use all registries for convenience", "*")
        self.gl.docs[BASE] = copy.deepcopy(policies()[0])
        self.gl.docs[BASE]["spec"]["background"] = True
        with self.assertRaises(Rejected): self.proposal()
        self.assertEqual(self.gl.writes, [])

    def test_commit_timeout_after_write_reconciles_without_duplicate(self):
        self.gl.timeout = "after:/repository/commits"
        self.assertEqual(self.rt.propose_policy_fix("Actual observed test evidence requires the registry correction", HEALTHY_PATTERN)["state"], "unknown")
        self.gl.timeout = None
        self.proposal()
        self.assertEqual(sum(p == "/repository/commits" for p, _ in self.gl.writes), 1)

    def test_commit_timeout_before_write_is_not_blindly_retried(self):
        self.gl.timeout = "before:/repository/commits"
        reason = "Actual observed test evidence requires the registry correction"
        self.rt.propose_policy_fix(reason, HEALTHY_PATTERN)
        self.gl.timeout = None
        self.assertEqual(self.rt.propose_policy_fix(reason, HEALTHY_PATTERN)["state"], "unknown")
        self.assertEqual(len(self.gl.writes), 1)

    def test_mr_timeout_reconciles_same_mr(self):
        self.gl.timeout = "after:/merge_requests"
        self.assertEqual(self.rt.propose_policy_fix("Actual observed test evidence requires the registry correction", HEALTHY_PATTERN)["state"], "unknown")
        self.gl.timeout = None
        self.assertEqual(self.rt.inspect_policy_fix()["binding"]["iid"], 1)
        self.assertEqual(len(self.gl.writes), 2)

    def test_latest_pipeline_and_required_tests_gate(self):
        self.proposal()
        self.gl.pipeline_status = "running"
        self.assertFalse(self.rt.inspect_policy_fix()["ci_pass"])
        self.gl.pipeline_status = "success"
        self.gl.missing_test = True
        self.assertFalse(self.rt.inspect_policy_fix()["ci_pass"])
        self.gl.missing_test = False
        self.gl.missing_report = True
        self.assertFalse(self.rt.inspect_policy_fix()["ci_pass"])

    def test_changed_head_and_extra_diff_reject(self):
        self.proposal()
        self.gl.diff_extra = True
        self.assertFalse(self.rt.inspect_policy_fix()["diff_valid"])
        self.gl.mr["sha"] = "d" * 40
        with self.assertRaises(Rejected): self.rt.inspect_policy_fix()

    def test_no_generic_approval_or_agent_approval(self):
        binding = self.proposal()
        self.review(binding)
        with self.assertRaises(Rejected): self.rt.control({"action": "authorize_merge", "binding": binding, "approved": True})
        with self.assertRaises(Rejected): self.rt.merge_policy_fix()
        self.assertEqual(len(self.gl.writes), 2)

    def test_exact_native_and_operator_receipts_then_sha_precondition(self):
        binding = self.proposal()
        self.authorize(binding)
        self.assertEqual(self.rt.merge_policy_fix()["state"], "merged")
        self.assertEqual(self.gl.writes[-1][1]["sha"], HEAD)
        self.rt.merge_policy_fix()
        self.assertEqual(len(self.gl.writes), 3)

    def test_changed_target_after_approval_blocks(self):
        binding = self.proposal()
        self.authorize(binding)
        self.gl.branches[self.cfg.target_branch] = "d" * 40
        self.gl.docs["d" * 40] = self.gl.faulty
        with self.assertRaises(Rejected): self.rt.merge_policy_fix()
        self.assertEqual(len(self.gl.writes), 2)

    def test_merge_timeout_readback_no_retry(self):
        binding = self.proposal()
        self.authorize(binding)
        self.gl.timeout = "after:/merge_requests/1/merge"
        self.assertEqual(self.rt.merge_policy_fix()["state"], "unknown")
        self.gl.timeout = None
        self.assertEqual(self.rt.merge_policy_fix()["state"], "merged")
        self.assertEqual(len(self.gl.writes), 3)

    def test_real_reads_are_fixed_and_trace_metadata_preserved(self):
        context = TraceContext.incoming("00-" + "a" * 32 + "-" + "b" * 16 + "-01", {"toolCallId": "actual-call", "taskId": "actual-task"})
        value = self.rt.invoke("read_kyverno_incident", {}, context)
        self.assertEqual(value["failed_create"][0]["event_id"], "event-uid")
        self.assertEqual(self.telemetry.calls[-1][0], self.cfg.kubernetes_service)
        self.assertEqual(self.telemetry.calls[-1][1], context)
        with self.assertRaises(Rejected): self.rt.invoke("read_kyverno_incident", {"namespace": "other"})

    def test_expired_authorization_blocks_merge(self):
        binding = self.proposal()
        self.authorize(binding)
        self.rt.now = lambda: NOW + 901
        with self.assertRaises(Rejected): self.rt.merge_policy_fix()
        self.assertEqual(len(self.gl.writes), 2)

    def test_reviewer_cannot_be_specialist_task(self):
        self.native_task()
        binding = self.proposal()
        with self.assertRaises(Rejected):
            self.rt.control({"action": "record_review", "binding": binding, "reviewer_id": self.cfg.reviewer_id,
                             "task_id": "native-specialist-task", "task_state": "COMPLETED", "verdict": "PASS",
                             "native_receipt_sha256": "1" * 64, "reviewed_at": NOW, "valid_admission": "pass", "invalid_admission": "pass"})


class RecoveryTests(BaseTest):
    def merged(self, native=True):
        binding = self.proposal()
        self.authorize(binding)
        self.rt.merge_policy_fix()
        if not native:
            del self.kube.policy["status"]["observedGeneration"]
        self.rt._http_probe = lambda: {"probe_id": "http-" + uuid.uuid4().hex, "observed_at": NOW,
                                      "status_code": 200, "body_sha256": self.cfg.expected_body_sha256}

    def receipt(self, active=False):
        r = {"receipt_id": "actual-test-probe-receipt", "run_id": self.cfg.run_id, "incident_id": self.cfg.incident_id,
             "source": "operator-kubernetes-dry-run", "source_receipt_sha256": "e" * 64, "merge_sha": MERGE,
             "policy_uid": "policy-uid", "generation": 3, "observed_generation": None if active else 3,
             "policy_spec_sha256": self.cfg.healthy_policy_spec_sha256,
             "observations": [{"probe_id": "post-" + str(i), "observed_at": NOW, "kind": "valid" if i < 3 else "invalid",
                               "result": "admitted" if i < 3 else "denied", "policy_name": self.cfg.policy_name, "rule_name": self.cfg.rule_name} for i in range(4)]}
        if active:
            meta = policy_read_metadata(self.kube.policy, NOW)
            r.update({"observation_method": POLICY_OBSERVATION_METHOD, "policy_read_before": meta, "policy_read_after": dict(meta)})
        return r

    def test_missing_merge_or_probe_receipts_wait(self):
        self.assertEqual(self.rt.verify_recovery()["state"], "waiting")
        self.merged()
        result = self.rt.verify_recovery()
        self.assertFalse(result["fixed"])
        self.assertTrue(any("receipts" in x for x in result["reasons"]))

    def test_complete_native_status_proof(self):
        self.merged()
        self.rt.control({"action": "record_probe_receipt", "receipt": self.receipt()})
        self.assertTrue(self.rt.verify_recovery()["fixed"])

    def test_explicit_active_variant_preserves_absent_native_field(self):
        self.merged(native=False)
        self.rt.control({"action": "record_probe_receipt", "receipt": self.receipt(active=True)})
        result = self.rt.verify_recovery()
        self.assertTrue(result["fixed"], result["reasons"])
        self.assertIsNone(result["policy"]["observed_generation"])
        self.assertEqual(result["active_probe_generation"], 3)
        self.assertEqual(result["policy_observation_method"], POLICY_OBSERVATION_METHOD)

    def test_active_bracket_mismatch_or_generation_change_block(self):
        self.merged(native=False)
        r = self.receipt(active=True)
        r["policy_read_after"]["generation"] = 4
        with self.assertRaises(Rejected): self.rt.control({"action": "record_probe_receipt", "receipt": r})
        self.rt.control({"action": "record_probe_receipt", "receipt": self.receipt(active=True)})
        self.kube.change_policy_on_second = True
        self.assertFalse(self.rt.verify_recovery()["fixed"])

    def test_invalid_probe_must_still_be_denied(self):
        self.merged()
        r = self.receipt()
        r["observations"][-1]["result"] = "admitted"
        self.rt.control({"action": "record_probe_receipt", "receipt": r})
        self.assertFalse(self.rt.verify_recovery()["fixed"])

    def test_probe_identity_remains_bound_after_newer_receipt(self):
        self.merged()
        original = self.receipt()
        self.rt.control({"action": "record_probe_receipt", "receipt": original})
        newer = copy.deepcopy(original)
        newer["receipt_id"] = "newer-receipt"
        for p in newer["observations"]: p["probe_id"] += "-new"
        self.rt.control({"action": "record_probe_receipt", "receipt": newer})
        changed = copy.deepcopy(original)
        changed["observations"][-1]["result"] = "admitted"
        with self.assertRaises(Rejected): self.rt.control({"action": "record_probe_receipt", "receipt": changed})

    def test_three_actual_http_reads_detect_failed_third_response(self):
        self.merged()
        self.rt.control({"action": "record_probe_receipt", "receipt": self.receipt()})
        seen = []
        class Application(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                seen.append(self.path)
                body = b"recovered\n"
                self.send_response(500 if len(seen) == 3 else 200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Application)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.rt.config = replace(self.cfg, application_url="http://127.0.0.1:" + str(server.server_port) + "/")
        self.rt._http_probe = Runtime._http_probe.__get__(self.rt, Runtime)
        result = self.rt.verify_recovery()
        self.assertEqual(len(seen), 3)
        self.assertFalse(result["fixed"])
        self.assertEqual([p["status_code"] for p in result["http_observations"]], [200, 200, 500])


class HTTPTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.runtime = self.rt
        self.server.tokens = {k: k + "-" + "x" * 40 for k in ("operator", "reviewer", "investigator")}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, route, value=None, role=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if role: headers["Authorization"] = "Bearer " + self.server.tokens[role]
        conn.request("POST" if value is not None else "GET", route, canonical(value) if value is not None else None, headers)
        response = conn.getresponse()
        raw = response.read()
        self.assertLessEqual(len(raw), 8192)
        status = response.status
        conn.close()
        return status, json.loads(raw)

    def test_health_public_state_operator_only(self):
        self.assertEqual(self.request("/healthz")[0], 200)
        self.assertEqual(self.request("/state")[0], 401)
        self.assertEqual(self.request("/state", role="reviewer")[0], 401)
        self.assertEqual(self.request("/state", role="operator")[0], 200)

    def test_reviewer_cannot_propose_or_use_other_endpoint(self):
        status, body = self.request("/mcp/reviewer", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "reviewer")
        self.assertEqual(status, 200)
        self.assertEqual({t["name"] for t in body["result"]["tools"]}, {"read_kyverno_incident", "read_policy_repository", "inspect_policy_fix"})
        status, _ = self.request("/mcp/reviewer", {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "propose_policy_fix", "arguments": {}}}, "reviewer")
        self.assertEqual(status, 400)
        self.assertEqual(self.request("/mcp/investigator", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, "reviewer")[0], 401)
        self.assertEqual(self.gl.writes, [])

    def test_oversized_inbound_and_arbitrary_args_rejected(self):
        self.assertEqual(self.request("/mcp/investigator", {"junk": "x" * 65536}, "investigator")[0], 400)
        _, body = self.request("/mcp/investigator", {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "read_policy_repository", "arguments": {"url": "https://other.invalid"}}}, "investigator")
        self.assertTrue(body["result"]["isError"])

    def test_dashboard_merge_discovery_and_call_are_disabled_by_default(self):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        status, result = self.request("/mcp/investigator", payload, "investigator")
        self.assertEqual(status, 200)
        self.assertNotIn("merge_dashboard_approved_fix", {tool["name"] for tool in result["result"]["tools"]})
        call = {**payload, "method": "tools/call", "params": {"name": "merge_dashboard_approved_fix", "arguments": {}}}
        self.assertEqual(self.request("/mcp/investigator", call, "investigator")[0], 400)
        with self.assertRaises(Rejected):
            self.rt.invoke("merge_dashboard_approved_fix", {})
        self.assertFalse(self.gl.writes)

    def test_dashboard_merge_enabled_for_investigator_only(self):
        self.rt.human_merger_ids, self.rt.dashboard_merge_enabled = (9,), True
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        _, result = self.request("/mcp/investigator", payload, "investigator")
        tools = {tool["name"]: tool for tool in result["result"]["tools"]}
        self.assertTrue(tools["merge_dashboard_approved_fix"]["annotations"]["destructiveHint"])
        _, result = self.request("/mcp/reviewer", payload, "reviewer")
        self.assertNotIn("merge_dashboard_approved_fix", {tool["name"] for tool in result["result"]["tools"]})
        for name in ("approve_dashboard", "record_dashboard_approval"):
            call = {**payload, "method": "tools/call", "params": {"name": name, "arguments": {}}}
            self.assertEqual(self.request("/mcp/investigator", call, "investigator")[0], 400)
        self.assertEqual(self.request("/control", {"action": "approve_dashboard", "approval": {}}, "investigator")[0], 401)

    def test_dashboard_native_context_must_match_operator_task(self):
        self.rt.human_merger_ids, self.rt.dashboard_merge_enabled = (9,), True
        self.ledger.patch({"flow_merge_task_binding": {"task_id": "real-task", "session_id": "real-session"}})
        context = TraceContext.incoming(metadata={"task_id": "different-task"})
        with self.assertRaises(Rejected):
            self.rt.invoke("merge_dashboard_approved_fix", {}, context)
        self.assertFalse(self.gl.writes)

    def test_trusted_dashboard_human_ids_are_validated(self):
        for principals in ([9], (9, 9), (True,), (0,), ("9",)):
            with self.subTest(principals=principals):
                with self.assertRaises(Rejected):
                    Runtime(self.cfg, self.ledger, self.gl, self.kube, self.telemetry, human_merger_ids=principals)

    def test_kubernetes_adapter_refuses_write_before_network(self):
        client = HTTPJSON("test", "https://example.invalid", read_only=True)
        with self.assertRaises(Rejected): client.request("/api", "POST", {})


class TelemetryTests(BaseTest):
    def test_actual_otlp_payload_server_kind_and_metadata_only(self):
        received = []
        class Capture(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
        server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        c = replace(self.cfg, otlp_endpoint="http://127.0.0.1:" + str(server.server_port))
        telemetry = Telemetry(c, self.ledger)
        ctx = TraceContext.incoming("00-" + "a" * 32 + "-" + "b" * 16 + "-01", {"toolCallId": "real-native-call"})
        self.assertTrue(telemetry.export(c.gitlab_service, ctx, "c" * 16, "MCP inspect_policy_fix", 1, values={"gen_ai.tool.name": "inspect_policy_fix"}))
        self.assertEqual([p for p, _ in received], ["/v1/traces", "/v1/logs"])
        span = received[0][1]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(span["kind"], 2)
        self.assertEqual(span["traceId"], "a" * 32)
        self.assertEqual(span["parentSpanId"], "b" * 16)
        self.assertNotIn("Authorization", json.dumps(received))
        self.assertNotIn("content", json.dumps(received))


class DashboardRuntimeTests(BaseTest):
    def test_operator_approval_then_actual_runtime_tool_uses_exact_sha_and_distinct_actor(self):
        from gitlab_lifecycle import Lifecycle
        self.rt = Runtime(self.cfg, self.ledger, self.gl, self.kube, self.telemetry,
                          now=lambda: NOW, human_merger_ids=(9,))
        binding = self.proposal()
        self.review(binding)
        issues = []
        original = self.gl.request
        def request(path, method="GET", body=None, traceparent=None):
            suffix = path.split("/projects/" + self.cfg.project_id, 1)[1]
            if suffix.startswith("/issues?"):
                return copy.deepcopy(issues)
            if suffix == "/issues" and method == "POST":
                issues.append({**body, "iid": 7, "project_id": int(self.cfg.project_id),
                               "state": "opened", "web_url": "https://gitlab.example/issues/7"})
                return copy.deepcopy(issues[-1])
            if suffix == "/issues/7":
                return copy.deepcopy(issues[0])
            result = original(path, method, body, traceparent)
            if suffix == "/merge_requests/1/merge":
                self.gl.mr.update({"merge_user": {"id": 17}, "merged_by": {"id": 17}})
            return result
        self.gl.request = request
        Lifecycle(self.rt, (9,)).ensure_ticket()
        approval = {"approval_id": "actual-dashboard-click", "binding": binding, "principal_id": 9,
                    "approved_at": NOW, "expires_at": NOW + 900}
        self.assertEqual(self.rt.control({"action": "approve_dashboard", "approval": approval}), approval)
        result = self.rt.invoke("merge_dashboard_approved_fix", {})
        self.assertEqual(result["state"], "reconciling")
        self.assertEqual(result["principal_id"], 9)
        self.assertEqual(result["gitlab_actor_id"], 17)
        self.assertEqual(self.rt.invoke("merge_dashboard_approved_fix", {}), result)
        merges = [body for path, body in self.gl.writes if path.endswith("/merge")]
        self.assertEqual(merges, [{"sha": HEAD, "should_remove_source_branch": False}])
        with self.assertRaises(Rejected):
            self.rt.merge_policy_fix()
        self.assertNotIn("native_approval_request", self.ledger.state())
        self.assertNotIn("human_authorization", self.ledger.state())
        self.assertNotIn("flow_human_merge", self.ledger.state())


if __name__ == "__main__":
    unittest.main()
