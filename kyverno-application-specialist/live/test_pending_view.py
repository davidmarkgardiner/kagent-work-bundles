"""The pre-merge projection cannot invent acceptance, approval or recovery."""
import copy
import unittest

from core import Rejected
from pending_view import build
from test_runtime import config


def inputs():
    c = config()
    b = {"project_id": c.project_id, "run_id": c.run_id, "incident_id": c.incident_id,
         "iid": 1, "head_sha": "b" * 40}
    ledger = {"state": {"proposal": {"binding": b, "created_at": 1700000070}},
              "outbox": {"status": "accepted", "task_id": "task-original", "message_id": "message-original", "candidate_id": "a" * 64}}
    candidate = {"candidate_id": "a" * 64, "observations": [
        {"probe": {"probe_id": "probe-" + str(i), "observed_at": 1700000000 + i * 30, "kind": "valid", "result": "denied"},
         "policy": {"policy_revision": "c" * 40}} for i in range(3)]}
    app = {"namespace": c.namespace, "deploymentName": c.application, "uid": "deployment-id",
           "observedAt": 1700000061, "recordedAt": 1700000061, "generation": 2,
           "observedGeneration": 2, "desiredReplicas": 1, "updatedReplicas": 0, "availableReplicas": 0}
    initial = {"id": "task-original", "contextId": "session-original", "status": {"state": "TASK_STATE_SUBMITTED"},
               "history": [{"messageId": "message-original"}]}
    current = {"id": "task-original", "contextId": "session-original", "status": {"state": "TASK_STATE_INPUT_REQUIRED"},
               "metadata": {"kagent.dev/a2a/task-created-at": "2023-11-14T22:14:22Z"}}
    inspection = {"binding": copy.deepcopy(b), "diff_valid": True, "policy_spec_sha256": c.healthy_policy_spec_sha256, "ci_pass": False}
    return [c, ledger, candidate, app, initial, current, inspection, {"traces": []}, 1700000080]


class PendingTests(unittest.TestCase):
    def test_submitted_receipt_without_timestamp_uses_actual_native_creation_metadata(self):
        plan, data = build(*inputs())
        self.assertEqual(data["receipts"]["investigation"]["recordedAt"], 1700000062)
        self.assertEqual(plan["binding"]["taskId"], "task-original")
        self.assertNotIn("approval", data["receipts"])
        self.assertNotIn("verification", data["receipts"])
        self.assertEqual(data["telemetry"], {})
        self.assertIn("Static CI: pending", data["summary"]["fix"])

    def test_different_original_message_is_not_accepted(self):
        values = inputs(); values[4]["history"][0]["messageId"] = "other-message"
        with self.assertRaises(Rejected):
            build(*values)

    def test_changed_inspected_head_is_rejected(self):
        values = inputs(); values[6]["binding"]["head_sha"] = "d" * 40
        with self.assertRaises(Rejected):
            build(*values)

    def test_missing_creation_time_is_not_invented(self):
        values = inputs(); values[5]["metadata"] = {}
        with self.assertRaises(Rejected):
            build(*values)

    def test_terminal_task_cannot_be_presented_as_pending_approval(self):
        values = inputs(); values[5]["status"]["state"] = "TASK_STATE_COMPLETED"
        with self.assertRaises(Rejected):
            build(*values)

    def test_post_decision_state_requires_another_observer(self):
        for key in ["human_authorization", "merged"]:
            values = inputs(); values[1]["state"][key] = {"decision": "approved"}
            with self.assertRaises(Rejected):
                build(*values)


if __name__ == "__main__":
    unittest.main()
