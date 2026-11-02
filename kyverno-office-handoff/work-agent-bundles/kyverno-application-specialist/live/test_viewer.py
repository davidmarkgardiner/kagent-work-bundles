"""Offline operator-file projection and actual UI checks; no cluster or spans created."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

FLOW = Path(__file__).resolve().parents[2] / "otel-agent-flow"
if str(FLOW) not in sys.path:
    sys.path.append(str(FLOW))

import viewer
from test_recovery import activity_store, valid_documents
from test_ui import UiBehaviorTests
from telemetry import ALLOWED

NOW = 1700000200


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        self.profile_path, self.status_path = directory / "admission.json", directory / "admission-status.json"
        self.scope = {"schema_version": 1, "run_id": "run-live", "incident_id": "incident-live", "cluster_id": "reviewed-cluster",
                      "namespace": "demo", "application": "app", "policy_name": "approved-registry", "rule_name": "image-rule",
                      "profile_revision": "a" * 64}
        self.status = {**self.scope, "captured_at": NOW, "valid_denials": 3, "classifier_attempts": 1,
                       "phase": "suppressed", "confidence": 0.93, "threshold": 0.95}
        self.write()

    def write(self):
        self.profile_path.write_text(json.dumps(self.scope))
        self.status_path.write_text(json.dumps(self.status))

    def project(self, now=NOW):
        self.write()
        return viewer.pre_admission_view(self.status_path, self.profile_path, now)

    def composed(self, activity=None, snapshot_path=None, profile_path=None, now=NOW):
        return viewer.recovery_view(activity or {}, snapshot_path or self.status_path.parent / "missing-snapshot.json",
                                    profile_path or self.status_path.parent / "missing-profile.json",
                                    self.status_path, self.profile_path, now)

    def test_matching_real_status_shows_denials_and_suppression_without_native_identity(self):
        view = self.project()
        self.assertEqual(view["preAdmissionScope"], self.scope)
        self.assertEqual(view["state"], "unknown")
        self.assertFalse(view["completeDemoProof"])
        self.assertNotIn("binding", view)
        self.assertNotIn("taskId", json.dumps(view))
        self.assertIn("3 known-good admission denials", view["summary"]["fault"])
        self.assertIn("confidence 0.93", view["summary"]["fix"])
        self.assertIn("threshold 0.95", view["summary"]["fix"])
        self.assertIn("Native task not yet verified", view["summary"]["fix"])
        self.assertEqual(view["telemetry"], {"state": "incomplete", "checks": []})

    def test_each_scope_field_must_match_separately_reviewed_profile(self):
        for field in viewer.ADMISSION_SCOPE:
            with self.subTest(field=field):
                before = deepcopy(self.status)
                self.status[field] = 2 if field == "schema_version" else "b" * 64 if field == "profile_revision" else "other"
                self.assertIsNone(self.project())
                self.status = before

    def test_stale_future_and_malformed_input_cannot_project(self):
        for field, value in (("captured_at", NOW - 301), ("captured_at", NOW + 1), ("captured_at", True),
                             ("valid_denials", -1), ("valid_denials", True), ("classifier_attempts", 13),
                             ("classifier_attempts", 1.5), ("phase", "recovered"), ("confidence", True),
                             ("confidence", 1.1), ("confidence", -0.1), ("confidence", float("nan")),
                             ("confidence", float("inf")), ("threshold", 0.93), ("threshold", True)):
            with self.subTest(field=field, value=value):
                before = deepcopy(self.status)
                self.status[field] = value
                self.assertIsNone(self.project())
                self.status = before
        self.status_path.write_bytes(b'x' * 65537)
        self.assertIsNone(viewer.pre_admission_view(self.status_path, self.profile_path, NOW))
        self.status_path.write_text('{"schema_version":1,"schema_version":1}')
        self.assertIsNone(viewer.pre_admission_view(self.status_path, self.profile_path, NOW))
        self.status_path.unlink()
        self.assertIsNone(viewer.pre_admission_view(self.status_path, self.profile_path, NOW))

    def test_unknown_fields_raw_text_and_false_green_flags_are_rejected(self):
        for field, value in (("binding", {"taskId": "fake-task"}), ("taskId", "fake-task"),
                             ("state", "recovered"), ("completeDemoProof", True),
                             ("summary", "private raw log"), ("headers", {"Authorization": "private"})):
            before = deepcopy(self.status)
            self.status[field] = value
            self.assertIsNone(self.project())
            self.status = before
        self.scope["raw_logs"] = "private"
        self.assertIsNone(self.project())

    def test_every_phase_including_accepted_remains_non_green(self):
        for phase in ("observing", "suppressed", "unknown", "accepted"):
            self.status["phase"] = phase
            self.status["confidence"] = None if phase == "unknown" else 0.99
            view = self.project()
            self.assertEqual(view["state"], "unknown")
            self.assertFalse(view["completeDemoProof"])
            self.assertIn("Native task not yet verified", view["summary"]["fix"])
            self.assertNotIn("No native task admitted", json.dumps(view))
            self.assertEqual(view["telemetry"]["checks"], [])
            self.assertFalse(any(stage["state"] == "passed" for stage in view["stages"]))
        self.status["captured_at"] = NOW - 300
        self.assertIsNotNone(self.project())

    def test_invalid_preadmission_preserves_original_unknown_projection(self):
        self.status["run_id"] = "mismatched"
        self.write()
        view = self.composed()
        self.assertEqual(view["state"], "unknown")
        self.assertNotIn("preAdmissionScope", view)

    def test_actual_full_native_recovery_projection_has_precedence(self):
        plan, snapshot = valid_documents(NOW)
        plan_path, snapshot_path = self.profile_path.parent / "profile.json", self.profile_path.parent / "recovery.json"
        plan_path.write_text(json.dumps(plan))
        snapshot_path.write_text(json.dumps(snapshot))
        activity = activity_store(NOW).snapshot()
        view = self.composed(activity, snapshot_path, plan_path)
        self.assertEqual(view["state"], "recovered")
        self.assertTrue(view["completeDemoProof"])
        self.assertEqual(view["binding"]["taskId"], "native-task-1")
        self.assertNotIn("preAdmissionScope", view)
        # A valid native chain missing retained telemetry must retain its own unknown stages.
        view = self.composed({}, snapshot_path, plan_path)
        self.assertEqual(view["state"], "unknown")
        self.assertEqual(len(view["stages"]), 12)
        self.assertNotIn("preAdmissionScope", view)

    def test_composition_uses_exact_fixed_files_and_original_read_view(self):
        with patch.object(viewer, "read_view", return_value={"state": "unknown"}) as full, patch.object(viewer, "pre_admission_view", return_value={"state": "unknown", "completeDemoProof": False}) as pending:
            viewer.recovery_view({"traces": []})
        full.assert_called_once_with('/data/recovery.json', '/profile/profile.json', {"traces": []}, None)
        pending.assert_called_once_with('/data/admission-status.json', '/profile/admission.json', None)


class PreAdmissionUiTests(unittest.TestCase):
    run_ui = UiBehaviorTests.run_ui

    def test_ui_shows_scope_without_a_native_task_or_green_or_new_spans(self):
        now = int(time.time())
        scope = {"schema_version": 1, "run_id": "real-run", "incident_id": "real-incident", "cluster_id": "lab",
                 "namespace": "demo", "application": "app", "policy_name": "image-policy", "rule_name": "rule",
                 "profile_revision": "a" * 64}
        # Shape is the actual viewer projection, exercised through its file reader.
        with tempfile.TemporaryDirectory() as directory:
            profile, status = Path(directory) / "scope.json", Path(directory) / "status.json"
            profile.write_text(json.dumps(scope))
            status.write_text(json.dumps({**scope, "captured_at": now, "valid_denials": 3, "classifier_attempts": 2,
                                         "phase": "unknown", "confidence": None, "threshold": 0.95}))
            projected = viewer.pre_admission_view(status, profile, now)
        state = {"revision": 0, "traces": [], "nativeActivities": {}, "invocation": {"status": "idle"},
                 "sessionActivity": None, "recovery": projected,
                 "runtime": {"readOnlyViewer": True, "executionTargets": [], "label": "Offline viewer"}}
        self.run_ui(state, r"""
          setView('recovery');
          assert.match($('recovery-scope').textContent,/real-incident/);
          assert.match($('recovery-scope').textContent,/native task not yet verified/);
          assert.doesNotMatch($('recovery-scope').textContent,/no native task admitted/);
          assert.doesNotMatch($('recovery-scope').textContent,/undefined/);
          assert.match($('recovery-fault').textContent,/3 known-good admission denials/);
          assert.match($('recovery-fix').textContent,/Classifier phase unknown/);
          assert.equal($('recovery-status').className.includes('recovered'),false);
          assert.equal($('recovery-logs').disabled,true);
          assert.equal(state.traces.length,0);
          assert.equal(calls.filter(c=>c.url==='/api/invoke').length,0);
          renderRecovery(state.recovery.expiresAt+1);
          assert.equal($('recovery-status').textContent,'Recovery unknown');
        """)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.now = int(time.time())
        self.plan, self.snapshot = valid_documents(self.now)
        self.profile_path, self.archive_path = self.directory / "profile.json", self.directory / "observed-traces.json"
        self.profile_path.write_text(json.dumps(self.plan))
        store = activity_store(self.now)
        self.activity = store.snapshot()
        self.trace = self.activity["traces"][0]
        first_span = self.trace["spans"][0]
        store.ingest_logs({"resourceLogs": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": first_span["service"]}}]},
            "scopeLogs": [{"logRecords": [{"timeUnixNano": first_span["startNs"], "traceId": self.trace["traceId"],
                "spanId": first_span["spanId"], "severityNumber": 9, "eventName": "gen_ai.input.messages",
                "body": {"stringValue": "PRIVATE_BODY_MUST_STAY_OMITTED"}, "attributes": [
                    {"key": "a2a.task.id", "value": {"stringValue": self.plan["binding"]["taskId"]}}]}]}]}]})
        self.log = store.logs_snapshot()["logs"][0]
        self.archive = {"schemaVersion": 1, "source": "received-otel-dashboard", "capturedAt": self.now,
                        "traces": [self.trace], "logs": [self.log]}

    def read(self):
        self.archive_path.write_text(json.dumps(self.archive))
        return viewer.observed_archive(self.archive_path, self.profile_path, self.now)

    def test_received_metadata_and_times_are_preserved_without_ingestion_or_mutation(self):
        self.assertEqual(viewer.ARCHIVE_ATTRIBUTES, ALLOWED)
        before = deepcopy(self.archive)
        accepted = self.read()
        self.assertIsNotNone(accepted)
        current = {**self.activity, "traces": [], "revision": 123, "lastReceivedAt": 99}
        merged = viewer.merge_observed_traces(current, accepted)
        retained = merged["traces"][0]
        self.assertEqual(retained.pop("retainedSource"), "operator-received-archive")
        self.assertEqual(retained, self.trace)
        self.assertEqual(merged["revision"], 123)
        self.assertEqual(merged["lastReceivedAt"], 99)
        self.assertEqual(self.archive, before)
        self.assertEqual(current["traces"], [])
        self.assertNotIn("PRIVATE_BODY_MUST_STAY_OMITTED", json.dumps(accepted))
        # Archive expiry is historical retention, not fabricated current health.
        self.assertIsNotNone(viewer.observed_archive(self.archive_path, self.profile_path, self.now + 10000))

    def test_current_trace_and_log_copies_win_without_restamping(self):
        accepted = self.read()
        current_trace = deepcopy(self.trace)
        current_trace["receivedAt"] += 10
        current_trace["status"] = "error"
        merged = viewer.merge_observed_traces({"traces": [current_trace]}, accepted)
        self.assertEqual(merged["traces"], [current_trace])
        self.assertNotIn("retainedSource", merged["traces"][0])
        current_log = {**self.log, "severity": "ERROR", "severityNumber": 17}
        merged_logs = viewer.merge_observed_logs({"logs": [current_log], "services": [], "retained": 1000, "matching": 500}, accepted)
        self.assertEqual(merged_logs["logs"], [current_log])
        self.assertEqual(merged_logs["retained"], 1)
        self.assertEqual(merged_logs["upstreamRetained"], 1000)
        self.assertEqual(merged_logs["upstreamMatching"], 500)

    def test_wrong_source_agent_task_scope_and_missing_fields_reject_archive(self):
        cases = [lambda a: a.update(source="fixture"), lambda a: a.update(capturedAt=self.now + 1),
                 lambda a: a["traces"][0]["nativeRuntimeIdentity"].update(agentId="other/agent"),
                 lambda a: a["traces"][0]["spans"][0]["attributes"].update({"a2a.task.id": "other-task"}),
                 lambda a: a["traces"][0]["spans"][0]["attributes"].update({"flow.run.id": "other-run"}),
                 lambda a: a["traces"][0]["spans"][0]["attributes"].update({"Authorization": "private"}),
                 lambda a: a["traces"][0]["spans"][0].pop("receivedAt"),
                 lambda a: a["traces"][0].pop("inputTokens"),
                 lambda a: a["traces"][0].update(traceId="0" * 32),
                 lambda a: a["traces"][0]["spans"][0].update(spanId="0" * 16),
                 lambda a: a["traces"][0]["spans"][0]["attributes"].update({"flow.simulated": True})]
        original = deepcopy(self.archive)
        for mutate in cases:
            self.archive = deepcopy(original)
            mutate(self.archive)
            self.assertIsNone(self.read())

    def test_trace_span_log_and_total_size_limits_are_fail_closed(self):
        original = deepcopy(self.archive)
        self.archive["traces"] *= 5
        self.assertIsNone(self.read())
        self.archive = deepcopy(original)
        self.archive["traces"][0]["spans"] *= 65
        self.assertGreater(len(self.archive["traces"][0]["spans"]), 512)
        self.assertIsNone(self.read())
        self.archive = deepcopy(original)
        self.archive["logs"] *= 257
        self.assertIsNone(self.read())
        self.archive_path.write_bytes(b'x' * (viewer.MAX_ARCHIVE + 1))
        self.assertIsNone(viewer.observed_archive(self.archive_path, self.profile_path, self.now))
        self.archive_path.write_text('{"schemaVersion":1,"schemaVersion":1}')
        self.assertIsNone(viewer.observed_archive(self.archive_path, self.profile_path, self.now))

    def test_logs_require_exact_accepted_trace_span_and_sanitized_shape(self):
        original = deepcopy(self.archive)
        for changes in ({"traceId": "9" * 32}, {"spanId": "9" * 16}, {"body": "private"},
                        {"message": "PRIVATE_RAW_CONTENT"}, {"timestampNs": "0"}, {"severityNumber": True}):
            self.archive = deepcopy(original)
            self.archive["logs"][0].update(changes)
            self.assertIsNone(self.read())
        self.archive = deepcopy(original)
        self.archive["logs"].append(deepcopy(self.log))
        self.assertIsNone(self.read())

    def test_logs_merge_exact_filters_services_counts_and_original_timestamps(self):
        accepted = self.read()
        current = {"logs": [], "services": ["other-service"], "retained": 1000, "matching": 0, "limit": 200}
        merged = viewer.merge_observed_logs(current, accepted, self.trace["traceId"], self.log["service"])
        record = deepcopy(merged["logs"][0])
        self.assertEqual(record.pop("retainedSource"), "operator-received-archive")
        self.assertEqual(record, self.log)
        self.assertEqual(merged["retained"], 1)
        self.assertEqual(merged["matching"], 1)
        self.assertEqual(merged["services"], sorted({"other-service", self.log["service"]}))
        self.assertEqual(viewer.merge_observed_logs(current, accepted, "9" * 32)["matching"], 0)
        self.assertEqual(viewer.merge_observed_logs(current, accepted, service="wrong")["logs"], [])
        self.assertEqual(current["logs"], [])

    def test_archived_actual_reference_metadata_joins_existing_recovery_without_new_spans(self):
        snapshot_path = self.directory / "recovery.json"
        snapshot_path.write_text(json.dumps(self.snapshot))
        activity = viewer.merge_observed_traces({**self.activity, "traces": []}, self.read())
        view = viewer.recovery_view(activity, snapshot_path, self.profile_path, now=self.now)
        self.assertEqual(view["state"], "recovered", view)
        self.assertTrue(view["completeDemoProof"])
        self.assertEqual(len(activity["traces"][0]["spans"]), len(self.trace["spans"]))
        self.assertEqual(activity["traces"][0]["receivedAt"], self.trace["receivedAt"])
        self.assertEqual(viewer.merge_observed_traces(self.activity, None), self.activity)

    def test_existing_read_only_endpoints_merge_before_projection_and_filter_logs(self):
        accepted = self.read()
        handler = viewer.Handler.__new__(viewer.Handler)
        replies = []
        handler.reply = lambda code, value, *args: replies.append((code, value))
        handler.received = lambda path: {**deepcopy(self.activity), "traces": []} if path == '/api/state' else {
            "logs": [], "services": [], "retained": 10, "matching": 0}
        handler.path = '/api/state'
        with patch.object(viewer, 'observed_archive', return_value=accepted), patch.object(viewer, 'recovery_view', return_value={"state": "unknown"}) as project:
            handler.do_GET()
        self.assertEqual(replies[-1][0], 200)
        self.assertEqual(project.call_args.args[0]['traces'][0]['traceId'], self.trace['traceId'])
        self.assertEqual(replies[-1][1]['traces'][0]['receivedAt'], self.trace['receivedAt'])
        handler.path = '/api/logs?traceId=' + self.trace['traceId'] + '&service=' + self.log['service']
        with patch.object(viewer, 'observed_archive', return_value=accepted):
            handler.do_GET()
        self.assertEqual(replies[-1][0], 200)
        self.assertEqual(replies[-1][1]['logs'][0]['timestampNs'], self.log['timestampNs'])
        self.assertEqual(replies[-1][1]['matching'], 1)
        self.assertEqual(viewer.merge_observed_logs({'logs': [], 'retained': 10}, {**accepted, 'logs': []}), {'logs': [], 'retained': 10})


if __name__ == "__main__":
    unittest.main()
