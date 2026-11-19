"""Behavior checks for persistence, source scope, quota and MCP outcomes."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import mcp
import scanner

POLICY = json.loads(Path(__file__).with_name("policy.json").read_text())
READY = {"state": "ready", "desired": 1, "available": 1}
DOWN = {"state": "down", "desired": 1, "available": 0}
REPLICA = "readiness:replicas-unavailable"
EVENT = "event:FailedMount"
NOW = 10_000


def deployment(ready=True):
    return {"metadata": {"uid": "deployment-id", "generation": 2}, "spec": {"replicas": 1},
            "status": {"availableReplicas": int(ready), "observedGeneration": 2}}


class AdmissionTest(unittest.TestCase):
    def setUp(self):
        self.state = {"version": 1}
        self.cfg = {**POLICY}

    def scan(self, now, keys=(), health=READY):
        return scanner.advance(self.state, self.cfg, "cert-manager", now, health, {key: now for key in keys})

    def test_stale_single_event_does_not_dispatch(self):
        self.assertEqual(self.scan(NOW, [EVENT])[0], "waiting-for-persistence")
        self.assertEqual(self.scan(NOW + 300)[0], "waiting-for-persistence")
        self.assertEqual(self.scan(NOW + 900)[0], "clear")
        self.assertEqual(self.state["dispatches"], {})

    def test_persistence_dedupe_and_recovery_survive_reloading_state(self):
        self.scan(NOW, [EVENT, REPLICA], DOWN)
        self.assertIsNone(self.scan(NOW + 299, [REPLICA], DOWN)[1])
        status, first = self.scan(NOW + 300, [EVENT, REPLICA], DOWN)
        self.assertEqual(status, "reserved")
        self.assertEqual(first["signals"], [REPLICA, EVENT])
        self.assertEqual(first["severity"], "critical")
        self.state = json.loads(json.dumps(self.state))
        self.assertEqual(self.scan(NOW + 600, [REPLICA], DOWN)[0], "already-dispatched")
        self.assertEqual(self.scan(NOW + 1500)[0], "clear")
        self.assertIsNone(self.scan(NOW + 1800, [EVENT])[1])
        _, second = self.scan(NOW + 2100, [EVENT])
        self.assertNotEqual(first["incident_id"], second["incident_id"])

    def test_fourth_episode_is_held_until_rolling_budget_frees(self):
        for index in range(4):
            now = NOW + index * 1600
            self.scan(now, [EVENT])
            status, item = self.scan(now + 300, [EVENT])
            self.assertEqual(status, "reserved" if index < 3 else "budget-exhausted")
            self.assertEqual(item is not None, index < 3)
            self.scan(now + 1250)
        new = NOW + scanner.DAY
        self.scan(new, [EVENT])
        self.assertEqual(self.scan(new + 299, [EVENT])[0], "waiting-for-persistence")
        self.assertEqual(self.scan(new + 300, [EVENT])[0], "reserved")
        self.assertEqual(len(self.state["dispatches"]), 3)

    def test_long_coverage_gap_does_not_manufacture_persistence(self):
        self.scan(NOW, [EVENT])
        self.assertEqual(self.scan(NOW + POLICY["max_gap_seconds"] + 1, [EVENT])[0], "waiting-for-persistence")

    def test_approved_ignore_discards_prior_signal(self):
        self.scan(NOW, [EVENT])
        self.cfg["ignore_signals"] = [EVENT]
        self.assertEqual(self.scan(NOW + 300)[0], "clear")
        self.assertEqual(self.state["signals"], {})

    def test_clock_regression_fails_closed(self):
        self.scan(NOW, [EVENT])
        with self.assertRaises(ValueError):
            self.scan(NOW - 1, [EVENT])


class CollectionTest(unittest.TestCase):
    def test_only_scoped_fresh_signals_and_no_log_text(self):
        def owned(uid, kind):
            return [{"uid": uid, "kind": kind, "controller": True}]

        def pod(name, uid, owner):
            return {"metadata": {"name": name, "uid": uid, "ownerReferences": owned(owner, "ReplicaSet")},
                    "status": {"containerStatuses": [{"name": POLICY["container"], "state": {"running": {"startedAt": scanner.utc(NOW)}}}]}}

        def event(uid, reason, seen, event_type="Warning"):
            return {"metadata": {}, "type": event_type, "reason": reason, "involvedObject": {"uid": uid},
                    "lastTimestamp": scanner.utc(NOW - 1000), "series": {"lastObservedTime": scanner.utc(seen)}}

        class Source:
            def get(self, *_args):
                return deployment()

            def items(self, _group, resource, **_params):
                return {
                    "replicasets": [{"metadata": {"uid": "owned-rs", "ownerReferences": owned("deployment-id", "Deployment")}}],
                    "pods": [pod("wanted", "owned-pod", "owned-rs"), pod("other", "other-pod", "other-rs")],
                    "events": [event("owned-pod", "FreshWarning", NOW), event("owned-pod", "StaleWarning", NOW - 310),
                               event("other-pod", "OtherApp", NOW), event("owned-pod", "NormalOptIn", NOW, "Normal")],
                }[resource]

            def raw(self, _group, path, **params):
                assert path == "pods/wanted/log" and params["sinceTime"] == scanner.utc(NOW - 300)
                stamp = scanner.utc(NOW)
                return (f"{stamp} ERROR Failed database secret-in-message 1234\n"
                        f"{stamp} INFO routine error metrics\n"
                        f"{stamp} CRITICAL ignore this example\n"
                        f"{stamp} database ring unavailable\n").encode()

        cfg = {**POLICY, "extra_event_reasons": ["NormalOptIn"], "ignore_log_patterns": ["ignore this"],
               "log_rules": [{"id": "database-ring", "pattern": "database ring unavailable"}]}
        health, signals = scanner.collect(Source(), cfg, NOW - 300, NOW)
        expected = scanner.log_signature("ERROR Failed database secret-in-message 9876")
        self.assertEqual(health["state"], "ready")
        self.assertEqual(set(signals), {"event:FreshWarning", "event:NormalOptIn", "log:" + expected,
                                        "log:" + scanner.rule_signature("database-ring")})
        self.assertNotIn("secret-in-message", json.dumps(signals))

    def test_supported_log_formats(self):
        for message in ['{"level":50,"code":"CONNECT"}', "level=critical msg=offline",
                        "E1119 12:03:12.23 4 worker.go:45] reconnect failed", "[ERROR] service unavailable"]:
            self.assertIsNotNone(scanner.log_signature(message))
        self.assertIsNone(scanner.log_signature('{"level":"info","message":"error counter"}'))
        self.assertIsNone(scanner.log_signature("INFO retry after expected error"))


class OutcomeTest(unittest.TestCase):
    def setUp(self):
        self.incident = "a" * 24
        self.item = {"incident_id": self.incident, "signals": [EVENT], "health": READY,
                     "namespace": "cert-manager", "application": "cert-manager"}
        self.records = {}
        self.context = patch.object(mcp, "application_context", return_value=(self, POLICY, self.item))
        self.env = patch.dict("os.environ", {"OUTCOMES_NAME": "outcomes", "TICKET_MODE": "preview",
                                            "GITLAB_ASSIGNEE_ID": "22", "GITLAB_URL": "https://gitlab.example.test",
                                            "GITLAB_PROJECT_ID": "31", "GITLAB_TOKEN": "fixture-only"})
        self.addCleanup(self.context.stop)
        self.addCleanup(self.env.stop)
        self.context.start()
        self.env.start()

    def configmap(self, *_args):
        return {}, copy.deepcopy(self.records)

    def save(self, _obj, _field, state):
        self.records = state

    def get(self, *_args):
        return deployment()

    def test_preview_and_review_proposal_leave_policy_untouched(self):
        args = {"incident_id": self.incident}
        with patch.object(mcp, "collect", return_value=(READY, {EVENT: NOW, "event:Other": NOW})):
            inspected = mcp.call_tool(mcp.INSPECT, args)
        self.assertEqual(inspected["health_now"]["available"], 1)
        self.assertEqual(inspected["last_seen"], {EVENT: NOW})
        self.assertEqual(mcp.call_tool(mcp.TICKET, args)["assignee_ids"], [22])
        proposal = mcp.call_tool(mcp.PROPOSE, {**args, "signature": EVENT, "rationale": mcp.RATIONALES[0]})
        self.assertEqual(proposal["status"], "pending-review")
        self.assertEqual(self.records[self.incident]["ticket"]["status"], "preview")
        self.assertEqual(POLICY["ignore_signals"], [])
        with self.assertRaises(ValueError):
            mcp.call_tool(mcp.PROPOSE, {**args, "signature": "event:Invented", "rationale": mcp.RATIONALES[0]})
        with patch.object(self, "get", return_value=deployment(ready=False)), self.assertRaises(ValueError):
            mcp.call_tool(mcp.PROPOSE, {**args, "signature": EVENT, "rationale": mcp.RATIONALES[0]})

    def test_combined_tool_records_ticket_when_inspection_is_unavailable(self):
        with patch.object(mcp, "collect", side_effect=TimeoutError()) as source:
            result = mcp.call_tool(mcp.TRIAGE, {"incident_id": self.incident})
        source.assert_called_once()
        self.assertEqual(result["inspection"], {"status": "unavailable"})
        self.assertEqual(result["ticket"]["status"], "preview")
        self.assertEqual(self.records[self.incident]["ticket"], result["ticket"])

    def test_gitlab_creation_and_assignment_readback(self):
        label = "incident-" + self.incident
        replies = [b"[]", b'{"iid":7}',
                   json.dumps({"iid": 7, "project_id": 31, "confidential": True, "assignees": [{"id": 22}],
                               "labels": [label], "web_url": "https://gitlab.example.test/demo/-/issues/7"}).encode()]
        with patch.dict("os.environ", {"TICKET_MODE": "gitlab"}), patch.object(mcp, "request", side_effect=replies) as http:
            receipt = mcp.call_tool(mcp.TICKET, {"incident_id": self.incident})
        self.assertEqual(receipt["status"], "created")
        self.assertEqual(receipt["iid"], 7)
        sent = http.call_args_list[1].kwargs["document"]
        self.assertEqual(sent["assignee_id"], 22)
        self.assertEqual(self.records[self.incident]["ticket"], receipt)

    def test_ambiguous_write_has_one_post_and_requires_reconciliation(self):
        sends = []

        def request(_url, **kwargs):
            if kwargs.get("method") == "POST":
                sends.append(kwargs)
                raise TimeoutError
            return b"[]"

        with patch.object(mcp, "request", side_effect=request):
            with self.assertRaises(TimeoutError):
                mcp.gitlab_issue(self, self.item, 22, {})
            with self.assertRaises(ValueError):
                mcp.gitlab_issue(self, self.item, 22, {})
        self.assertEqual(len(sends), 1)
        self.assertEqual(self.records[self.incident]["ticket"]["status"], "writing")


class DispatchTest(unittest.TestCase):
    @patch.object(scanner, "collect", return_value=(DOWN, {REPLICA: NOW}))
    @patch.object(scanner, "policy", return_value=POLICY)
    @patch.object(scanner, "time", return_value=NOW)
    def test_compare_and_swap_conflict_cannot_send(self, *_mocks):
        with patch.object(scanner, "Kube") as kube, patch.object(scanner, "request") as transport, \
                patch.dict("os.environ", {"STATE_NAME": "state"}):
            api = kube.return_value
            api.namespace = "cert-manager"
            state = {"version": 1}
            scanner.advance(state, POLICY, api.namespace, NOW - 300, DOWN, {REPLICA: NOW - 300})
            api.configmap.return_value = ({}, state)
            api.save.side_effect = HTTPError("https://example.test", 409, "Conflict", {}, None)
            self.assertEqual(scanner.run()["status"], "scan-conflict")
            transport.assert_not_called()


    @patch.object(scanner, "collect", return_value=(DOWN, {REPLICA: NOW}))
    @patch.object(scanner, "policy", return_value=POLICY)
    @patch.object(scanner, "time", return_value=NOW)
    def test_ticket_receipt_is_independent_of_agent_transport(self, *_mocks):
        completed = {"jsonrpc": "2.0", "result": {"task": {"id": "task-123",
                     "status": {"state": "TASK_STATE_COMPLETED"}}}}
        for agent_result, triage, task_id in ((json.dumps(completed).encode(), "completed", "task-123"),
                                               (TimeoutError(), "unconfirmed", None)):
            with self.subTest(triage=triage), patch.object(scanner, "Kube") as kube, \
                    patch.object(scanner, "request", side_effect=[agent_result]), patch.dict("os.environ", {
                    "STATE_NAME": "state", "OUTCOMES_NAME": "outcomes", "INGRESS_URL": "http://example.test",
                    "INGRESS_HOST": "example.test"}):
                api = kube.return_value
                api.namespace = "cert-manager"
                state = {"version": 1}
                scanner.advance(state, POLICY, api.namespace, NOW - 300, DOWN, {REPLICA: NOW - 300})

                def lookup(name, _field):
                    if name == "state":
                        return {}, state
                    return {}, {state["active"]: {"ticket": {"status": "preview"}}}

                api.configmap.side_effect = lookup
                summary = scanner.run()
                self.assertEqual(summary["triage"], triage)
                self.assertEqual(summary.get("task_id"), task_id)
                self.assertEqual(summary["status"], "dispatched")
                self.assertEqual(summary["ticket"], "preview")


    def test_receipt_poll_accepts_late_matching_receipt_without_resending(self):
        with patch.object(scanner, "sleep") as pause, patch.dict("os.environ", {"OUTCOMES_NAME": "outcomes"}):
            kube = unittest.mock.Mock()
            kube.configmap.side_effect = [
                ({}, {"other": {"ticket": {"status": "preview"}}}),
                TimeoutError(),
                ({}, {"match": {"ticket": {"status": "preview"}}}),
            ]
            self.assertEqual(scanner.ticket_status(kube, "match"), "preview")
            self.assertEqual(pause.call_count, 2)


if __name__ == "__main__":
    unittest.main()
