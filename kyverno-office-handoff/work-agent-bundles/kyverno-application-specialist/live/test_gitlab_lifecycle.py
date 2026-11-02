import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest

from core import APIError, Ledger, Rejected
from gitlab_lifecycle import Lifecycle


class FakeRuntime:
    def __init__(self, ledger):
        self.ledger, self.lock, self.calls = ledger, threading.RLock(), []
        self.config = SimpleNamespace(project_id="42", run_id="run-a", incident_id="incident-a", fix_branch="fix",
                                      target_branch="main", reviewer_id="reviewer", investigator_id="investigator",
                                      evidence_max_age_seconds=300, healthy_policy_spec_sha256="a" * 64,
                                      expected_http_status=200, expected_body_sha256="b" * 64)
        self.clock = 1000
        self.now = lambda: self.clock
        self.issues, self.create_mode, self.close_mode = [], "success", "success"
        self.binding = {"project_id": "42", "run_id": "run-a", "incident_id": "incident-a", "iid": 3,
                        "head_sha": "c" * 40, "base_sha": "d" * 40, "base_file_sha": "d" * 40}
        self.mr = {"iid": 3, "state": "merged", "sha": "c" * 40, "source_branch": "fix", "target_branch": "main",
                   "source_project_id": 42, "target_project_id": 42, "merge_commit_sha": "e" * 40,
                   "merge_user": {"id": 9}, "merged_by": {"id": 9}, "merged_at": "2026-11-01T10:00:00Z",
                   "web_url": "https://gitlab.example/mr/3"}
        self.info = {"binding": self.binding, "state": "merged", "ci_pass": True, "diff_valid": True, "draft": False}
        self.target = "e" * 40
        self.verify_calls = 0
        self.result = {"fixed": True, "state": "verified", "reasons": [], "merge_sha": "e" * 40,
                       "policy": {"uid": "policy-uid", "policy_spec_sha256": "a" * 64,
                                  "generation": 2, "observed_generation": None},
                       "policy_observation_method": "stable-policy-read-active-admission", "active_probe_generation": 2,
                       "deployment": {"uid": "deployment-uid"}, "verified_at": 1000}

    def _gl(self, path, method="GET", body=None):
        self.calls.append((path, method, body))
        if path.startswith("/issues?") and method == "GET":
            return copy.deepcopy(self.issues)
        if path == "/issues" and method == "POST":
            if self.create_mode != "lost":
                self.issues.append({"iid": 7, "project_id": 42, "web_url": "https://gitlab.example/issues/7",
                                    "state": "opened", **body})
            if self.create_mode != "success":
                raise APIError("GitLab")
            return copy.deepcopy(self.issues[-1])
        if path == "/issues/7":
            if method == "PUT":
                if self.close_mode != "lost":
                    self.issues[0]["state"] = "closed"
                if self.close_mode != "success":
                    raise APIError("GitLab")
            return copy.deepcopy(self.issues[0])
        if path == "/merge_requests/3" and method == "GET":
            return copy.deepcopy(self.mr)
        raise AssertionError((path, method, body))

    def inspect_policy_fix(self):
        return copy.deepcopy(self.info)

    def _branch_head(self, branch):
        return self.target

    def verify_recovery(self):
        self.verify_calls += 1
        return copy.deepcopy(self.result)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.temp.name) / "state.db", "identity")
        self.rt = FakeRuntime(self.ledger)
        self.flow = Lifecycle(self.rt, (9,))
        self.ledger.patch({"proposal": {"binding": self.rt.binding}, "review": {
            "binding": self.rt.binding, "verdict": "PASS", "reviewer_id": "reviewer"}})

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_closed_unmerged_repair_is_terminal(self):
        self.rt.mr['state']='closed'
        with self.assertRaises(Rejected):
            self.flow.observe_human_merge()

    def ready(self):
        self.flow.ensure_ticket()
        self.rt.clock = 900
        self.flow.observe_human_merge()
        self.rt.clock = 1000
        observations = [{"observed_at": at, "valid": {"receipt_id": f"valid-{at}", "result": "admitted"},
                         "invalid": {"receipt_id": f"invalid-{at}", "result": "denied"},
                         "http": {"probe_id": f"http-{at}", "status_code": 200, "body_sha256": "b" * 64}}
                        for at in (930, 960, 990)]
        self.ledger.patch({"flow_baseline": {"policy_uid": "policy-uid", "deployment_uid": "deployment-uid"},
                           "flow_verification_binding": {"task_id": "task-verify", "session_id": "session-verify"},
                           "flow_recovery_window": {"merge_sha": "e" * 40, "policy_uid": "policy-uid",
                               "deployment_uid": "deployment-uid", "policy_spec_sha256": "a" * 64,
                               "started_at": 930, "ended_at": 990, "observations": observations}})
        return {"id": "task-verify", "contextId": "session-verify", "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [{"parts": [{"data": {"id": "tool-actual", "name": "verify_recovery",
                    "response": {"output": json.dumps(self.rt.result)}},
                    "metadata": {"kagent.dev/a2a/part-type": "function_response"}}]}]}

    def writes(self, method):
        return [call for call in self.rt.calls if call[1] == method]

    def test_create_once_and_journal_precedes_post(self):
        original = self.rt._gl
        def guarded(path, method="GET", body=None):
            if method == "POST":
                self.assertIsNotNone(self.ledger.operation("flow-ticket-create"))
            return original(path, method, body)
        self.rt._gl = guarded
        first = self.flow.ensure_ticket()
        self.assertEqual(first, self.flow.ensure_ticket())
        self.assertEqual(len(self.writes("POST")), 1)
        self.assertEqual(self.ledger.state()["flow_ticket"]["iid"], 7)

    def test_uncertain_create_found_is_adopted_without_repeat(self):
        self.rt.create_mode = "committed-error"
        self.assertEqual(self.flow.ensure_ticket()["iid"], 7)
        self.assertEqual(self.flow.ensure_ticket()["iid"], 7)
        self.assertEqual(len(self.writes("POST")), 1)

    def test_uncertain_missing_create_never_reposts_even_after_restart(self):
        self.rt.create_mode = "lost"
        self.assertEqual(self.flow.ensure_ticket()["state"], "unknown")
        flow = Lifecycle(self.rt, (9,))
        self.assertEqual(flow.ensure_ticket()["state"], "unknown")
        self.assertEqual(len(self.writes("POST")), 1)

    def test_duplicate_mismatching_project_or_description_block(self):
        self.flow.ensure_ticket()
        original = copy.deepcopy(self.rt.issues[0])
        for issues in ([original, original], [{**original, "project_id": 43}], [{**original, "description": "other"}]):
            with self.subTest(issues=issues):
                self.rt.issues = issues
                with self.assertRaises(Rejected):
                    self.flow.ensure_ticket()
        self.assertEqual(len(self.writes("POST")), 1)

    def test_human_observation_needs_no_native_approval_and_never_merges(self):
        result = self.flow.observe_human_merge()
        self.assertEqual(result["state"], "reconciling")
        state = self.ledger.state()
        self.assertEqual(state["flow_human_merge"]["actor_id"], 9)
        self.assertEqual(set(state["merged"]), {"binding", "merge_sha", "merged_at", "observed_at", "url"})
        self.assertNotIn("human_authorization", state)
        self.assertNotIn("native_approval_request", state)
        self.assertFalse(self.writes("PUT"))
        self.assertFalse(self.writes("POST"))

    def test_waits_for_real_merge(self):
        self.rt.mr["state"] = "opened"
        self.assertEqual(self.flow.observe_human_merge()["state"], "waiting_human")
        self.assertNotIn("merged", self.ledger.state())

    def test_unauthorized_or_inconsistent_merger_blocks(self):
        for mr in ({"merge_user": {"id": 11}, "merged_by": {"id": 11}}, {"merged_by": {"id": 11}}):
            with self.subTest(mr=mr):
                self.rt.mr.update(mr)
                with self.assertRaises(Rejected):
                    self.flow.observe_human_merge()
        self.assertNotIn("merged", self.ledger.state())

    def test_changed_head_or_wrong_project_or_target_branch_blocks(self):
        original = copy.deepcopy(self.rt.mr)
        for patch in ({"sha": "f" * 40}, {"source_project_id": 55}, {"target_branch": "elsewhere"},
                      {"merge_commit_sha": "invalid"}):
            with self.subTest(patch=patch):
                self.rt.mr = {**original, **patch}
                with self.assertRaises(Rejected):
                    self.flow.observe_human_merge()
        self.rt.mr = original
        self.rt.target = "f" * 40
        with self.assertRaises(Rejected):
            self.flow.observe_human_merge()

    def test_missing_ci_diff_or_independent_review_blocks(self):
        for field in ("ci_pass", "diff_valid"):
            self.rt.info[field] = False
            with self.assertRaises(Rejected):
                self.flow.observe_human_merge()
            self.rt.info[field] = True
        self.ledger.patch({"review": {"binding": self.rt.binding, "verdict": "PASS", "reviewer_id": "investigator"}})
        with self.assertRaises(Rejected):
            self.flow.observe_human_merge()

    def test_second_mr_readback_catches_head_change(self):
        original = self.rt._gl
        count = 0
        def changing(path, method="GET", body=None):
            nonlocal count
            if path == "/merge_requests/3":
                count += 1
                if count == 2:
                    self.rt.mr["sha"] = "f" * 40
            return original(path, method, body)
        self.rt._gl = changing
        with self.assertRaises(Rejected):
            self.flow.observe_human_merge()

    def test_closes_after_terminal_native_and_fresh_runtime_and_window(self):
        task = self.ready()
        result = self.flow.close_verified_ticket(task)
        self.assertEqual(result["state"], "closed")
        self.assertEqual(self.rt.verify_calls, 1)
        self.assertEqual(self.writes("PUT"), [("/issues/7", "PUT", {"state_event": "close"})])
        self.assertEqual(self.flow.close_verified_ticket(task), result)
        self.assertEqual(len(self.writes("PUT")), 1)
        self.assertIsNone(self.rt.result["policy"]["observed_generation"])

    def test_closure_journal_precedes_put_and_uncertain_close_is_read_back(self):
        task = self.ready()
        original = self.rt._gl
        def guarded(path, method="GET", body=None):
            if method == "PUT":
                self.assertIsNotNone(self.ledger.operation("flow-ticket-close"))
            return original(path, method, body)
        self.rt._gl = guarded
        self.rt.close_mode = "committed-error"
        self.assertEqual(self.flow.close_verified_ticket(task)["state"], "closed")
        self.assertEqual(len(self.writes("PUT")), 1)

    def test_uncertain_close_never_retries_put(self):
        task = self.ready()
        self.rt.close_mode = "lost"
        self.assertEqual(self.flow.close_verified_ticket(task)["state"], "unknown")
        self.assertEqual(self.flow.close_verified_ticket(task)["state"], "unknown")
        self.assertEqual(len(self.writes("PUT")), 1)

    def test_missing_terminal_task_or_wrong_binding_cannot_close(self):
        task = self.ready()
        for patch in ({"status": {"state": "TASK_STATE_INPUT_REQUIRED"}}, {"id": "other"},
                      {"contextId": "other"}, {"artifacts": []}):
            with self.subTest(patch=patch):
                with self.assertRaises(Rejected):
                    self.flow.close_verified_ticket({**task, **patch})
        self.assertFalse(self.writes("PUT"))

    def test_user_text_or_forged_artifact_type_cannot_close(self):
        task = self.ready()
        part = task["artifacts"][0]["parts"][0]
        part["metadata"] = {}
        task["history"] = [{"role": "ROLE_USER", "parts": [{"text": json.dumps(self.rt.result)}]}]
        with self.assertRaises(Rejected):
            self.flow.close_verified_ticket(task)
        self.assertFalse(self.writes("PUT"))

    def test_stale_failed_incomplete_short_or_replayed_window_cannot_close(self):
        task = self.ready()
        original = self.ledger.state()["flow_recovery_window"]
        changes = []
        stale = copy.deepcopy(original); stale["observations"][0]["observed_at"] = 600; changes.append(stale)
        failed = copy.deepcopy(original); failed["observations"][1]["http"]["status_code"] = 503; changes.append(failed)
        denied = copy.deepcopy(original); denied["observations"][1]["invalid"]["result"] = "admitted"; changes.append(denied)
        incomplete = copy.deepcopy(original); incomplete["observations"][1].pop("valid"); changes.append(incomplete)
        short = copy.deepcopy(original); short["observations"][-1]["observed_at"] = 980; short["ended_at"] = 980; changes.append(short)
        replay = copy.deepcopy(original); replay["observations"][1]["http"]["probe_id"] = "http-930"; changes.append(replay)
        for window in changes:
            with self.subTest(window=window):
                self.ledger.patch({"flow_recovery_window": window})
                with self.assertRaises(Rejected):
                    self.flow.close_verified_ticket(task)
        self.assertFalse(self.writes("PUT"))

    def test_fresh_corroboration_failure_and_baseline_replacement_block(self):
        task = self.ready()
        original = copy.deepcopy(self.rt.result)
        for patch in ({"fixed": False}, {"verified_at": 600}, {"verified_at": 980}, {"merge_sha": "f" * 40},
                      {"policy": {"uid": "replacement", "policy_spec_sha256": "a" * 64}},
                      {"deployment": {"uid": "replacement"}}):
            with self.subTest(patch=patch):
                self.rt.result = {**original, **patch}
                with self.assertRaises(Rejected):
                    self.flow.close_verified_ticket(task)
        self.assertFalse(self.writes("PUT"))

    def test_merge_and_ci_alone_cannot_close(self):
        self.flow.ensure_ticket()
        self.flow.observe_human_merge()
        with self.assertRaises(Rejected):
            self.flow.close_verified_ticket({"status": {"state": "TASK_STATE_COMPLETED"}})
        self.assertFalse(self.writes("PUT"))




class DashboardApprovalTests(unittest.TestCase):
    setUp = LifecycleTests.setUp
    tearDown = LifecycleTests.tearDown
    writes = LifecycleTests.writes

    def prepare(self):
        self.rt.dashboard_merge_enabled, self.rt.human_merger_ids = True, (9,)
        self.rt.config.faulty_policy_sha256 = __import__('core').digest({"fixture": "faulty"})
        self.rt._manifest = lambda head: ({"fixture": "faulty"}, "d" * 40)
        self.rt._branch_head = lambda branch: self.rt.binding["head_sha"] if branch == "fix" else self.rt.target
        self.rt.target = self.rt.binding["base_sha"]
        self.rt.mr.update({"state": "opened", "merge_user": None, "merged_by": None, "merge_commit_sha": None})
        self.rt.info["state"] = "opened"
        self.rt.merge_mode = "success"
        self.flow.ensure_ticket()
        self.ledger.patch({"flow_merge_task_binding": {"task_id": "native-merge-task", "session_id": "native-merge-session"}})
        original = self.rt._gl
        def gitlab(path, method="GET", body=None):
            if path != "/merge_requests/3/merge" or method != "PUT":
                return original(path, method, body)
            self.assertIsNotNone(self.ledger.operation("flow-dashboard-merge"))
            self.assertEqual(body, {"sha": self.rt.binding["head_sha"], "should_remove_source_branch": False})
            self.rt.calls.append((path, method, body))
            if self.rt.merge_mode != "lost":
                self.rt.mr.update({"state": "merged", "merge_user": {"id": 17}, "merged_by": {"id": 17},
                                   "merge_commit_sha": "e" * 40, "merged_at": "2026-11-01T10:00:00Z"})
                self.rt.info["state"] = "merged"
                self.rt.target = "e" * 40
            if self.rt.merge_mode != "success":
                raise APIError("GitLab")
            return copy.deepcopy(self.rt.mr)
        self.rt._gl = gitlab
        return {"approval_id": "click-uuid", "binding": copy.deepcopy(self.rt.binding), "principal_id": 9,
                "approved_at": 1000, "expires_at": 1900}

    def test_approval_is_public_immutable_and_durable_without_native_receipts(self):
        approval = self.prepare()
        result = self.flow.approve_dashboard(approval)
        self.assertEqual(result, approval)
        result["binding"]["head_sha"] = "f" * 40
        self.assertEqual(self.flow.approve_dashboard(approval), approval)
        for patch in ({"approval_id": "replacement"}, {"expires_at": 1901}, {"principal_id": 10}):
            with self.assertRaises(Rejected):
                self.flow.approve_dashboard({**approval, **patch})
        self.ledger.close()
        self.ledger = Ledger(Path(self.temp.name) / "state.db", "identity")
        self.rt.ledger = self.ledger
        self.flow = Lifecycle(self.rt, (9,))
        self.assertEqual(self.flow.approve_dashboard(approval), approval)
        state = self.ledger.state()
        self.assertNotIn("human_authorization", state)
        self.assertNotIn("native_approval_request", state)
        self.assertFalse(self.writes("PUT"))

    def test_disabled_unknown_principal_expiry_and_wrong_binding_cannot_approve(self):
        approval = self.prepare()
        for patch in ({"principal_id": 10}, {"principal_id": True}, {"approved_at": 1001},
                      {"expires_at": 1000}, {"expires_at": 1901}, {"binding": {**approval["binding"], "run_id": "other"}}):
            with self.subTest(patch=patch), self.assertRaises(Rejected):
                self.flow.approve_dashboard({**approval, **patch})
        self.rt.dashboard_merge_enabled = False
        with self.assertRaises(Rejected):
            self.flow.approve_dashboard(approval)
        self.assertNotIn("flow_dashboard_approval", self.ledger.state())

    def test_requires_open_ticket_exact_ci_and_independent_review(self):
        approval = self.prepare()
        for field in ("ci_pass", "diff_valid"):
            self.rt.info[field] = False
            with self.assertRaises(Rejected):
                self.flow.approve_dashboard(approval)
            self.rt.info[field] = True
        self.rt.issues[0]["state"] = "closed"
        with self.assertRaises(Rejected):
            self.flow.approve_dashboard(approval)
        self.rt.issues[0]["state"] = "opened"
        self.ledger.patch({"review": {"binding": self.rt.binding, "verdict": "PASS", "reviewer_id": "investigator"}})
        with self.assertRaises(Rejected):
            self.flow.approve_dashboard(approval)

    def test_agent_merges_once_actor_is_distinct_from_human_and_no_native_approval_is_forged(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        result = self.flow.merge_dashboard_approved_fix()
        self.assertEqual(result["state"], "reconciling")
        self.assertEqual(result["principal_id"], 9)
        self.assertEqual(result["gitlab_actor_id"], 17)
        self.assertEqual(self.flow.merge_dashboard_approved_fix(), result)
        self.assertEqual(len(self.writes("PUT")), 1)
        state = self.ledger.state()
        self.assertNotIn("flow_human_merge", state)
        self.assertNotIn("native_approval_request", state)
        self.assertNotIn("human_authorization", state)
        self.assertEqual(state["merged"]["merge_sha"], "e" * 40)

    def test_unknown_operation_reads_exact_mr_and_branches_never_repeats_put(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        self.rt.merge_mode = "lost"
        self.assertEqual(self.flow.merge_dashboard_approved_fix()["state"], "unknown")
        self.rt.clock = 3000
        self.assertEqual(self.flow.merge_dashboard_approved_fix()["state"], "unknown")
        self.assertEqual(len(self.writes("PUT")), 1)
        self.rt.target = "f" * 40
        with self.assertRaises(Rejected):
            self.flow.merge_dashboard_approved_fix()
        self.assertEqual(len(self.writes("PUT")), 1)

    def test_committed_error_reconciles_after_expiry_without_second_put(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        self.rt.merge_mode = "committed-error"
        self.assertEqual(self.flow.merge_dashboard_approved_fix()["state"], "reconciling")
        self.rt.clock = 3000
        self.assertEqual(self.flow.observe_dashboard_merge()["state"], "reconciling")
        self.assertEqual(len(self.writes("PUT")), 1)

    def test_approval_expires_only_before_intent(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        self.rt.clock = 1900
        with self.assertRaises(Rejected):
            self.flow.merge_dashboard_approved_fix()
        self.assertFalse(self.writes("PUT"))
        self.assertIsNone(self.ledger.operation("flow-dashboard-merge"))

    def test_changed_ci_review_source_or_target_cannot_merge(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        self.rt.info["pipeline"] = {"id": 2}
        with self.assertRaises(Rejected):
            self.flow.merge_dashboard_approved_fix()
        self.rt.info.pop("pipeline")
        self.rt.target = "f" * 40
        with self.assertRaises(Rejected):
            self.flow.merge_dashboard_approved_fix()
        self.rt.target = "d" * 40
        self.ledger.patch({"review": {**self.ledger.state()["review"], "task_id": "replacement-review"}})
        with self.assertRaises(Rejected):
            self.flow.merge_dashboard_approved_fix()
        self.assertFalse(self.writes("PUT"))

    def test_optional_task_binding_is_immutable_after_intent(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        self.rt.merge_mode = "lost"
        self.flow.merge_dashboard_approved_fix()
        self.ledger.patch({"flow_merge_task_binding": {"task_id": "different-task", "session_id": "native-merge-session"}})
        with self.assertRaises(Rejected):
            self.flow.merge_dashboard_approved_fix()
        self.assertEqual(len(self.writes("PUT")), 1)

    def test_missing_intent_or_actual_actor_or_target_cannot_observe_success(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        with self.assertRaises(Rejected):
            self.flow.observe_dashboard_merge()
        self.rt.merge_mode = "lost"
        self.flow.merge_dashboard_approved_fix()
        self.rt.mr.update({"state": "merged", "merge_commit_sha": "e" * 40})
        self.rt.info["state"] = "merged"
        self.rt.target = "e" * 40
        with self.assertRaises(Rejected):
            self.flow.observe_dashboard_merge()
        self.assertNotIn("merged", self.ledger.state())


    def test_confirmed_operation_survives_crash_before_canonical_state_patch(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        result = self.flow.merge_dashboard_approved_fix()
        self.ledger.patch({"merged": None, "flow_dashboard_merge": None})
        self.rt.clock = 1500
        self.assertEqual(self.flow.observe_dashboard_merge(), result)
        self.assertEqual(len(self.writes("PUT")), 1)

    def test_task_binding_can_arrive_after_the_merge_without_racing_authorization(self):
        approval = self.prepare()
        self.flow.approve_dashboard(approval)
        self.ledger.patch({"flow_merge_task_binding": {}})
        result = self.flow.merge_dashboard_approved_fix()
        self.assertEqual(result["state"], "reconciling")
        self.assertEqual(result["merge_task_binding"], {})
        self.ledger.patch({"flow_merge_task_binding": {"task_id": "actual-task", "session_id": "actual-session"}})
        self.assertEqual(self.flow.observe_dashboard_merge(), result)
        self.assertEqual(len(self.writes("PUT")), 1)


if __name__ == "__main__":
    unittest.main()
