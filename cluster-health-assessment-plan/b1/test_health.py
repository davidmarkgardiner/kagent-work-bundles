import itertools
import json
import os
import sys
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from collector import (
    ALLOWED_WARNING_REASONS,
    Api,
    collapse_fox_findings,
    fox_state_findings,
    fox_symptom_family,
    hygiene_summary,
    load_config,
    native_group_count,
    node_headroom_watch,
    safe_section,
    workload_inventory,
)
from accelerated_qualification import replay
from calibration import LONDON, audit, expected_slots
from health import (
    DOMAIN_ORDER,
    canonical_checksum,
    counter_delta,
    display_score,
    evaluate_gate,
    event_timestamp,
    is_successful_job_pod,
    problem_key,
    recent_termination,
    stable_owner,
)


def domains(statuses):
    return {name: {"status": status} for name, status in zip(DOMAIN_ORDER, statuses)}


class PolicyTests(unittest.TestCase):
    def test_all_1024_domain_combinations(self):
        statuses = ("healthy", "watch", "degraded", "critical")
        seen = 0
        for combination in itertools.product(statuses, repeat=5):
            current = domains(combination)
            first = evaluate_gate(current, True, {})
            second = evaluate_gate(current, True, {"active": first["active"], "degraded_streak": first["degraded_streak"], "recovery_streak": first["recovery_streak"]})
            if "critical" in combination:
                self.assertTrue(first["active"], combination)
            elif "degraded" in combination:
                self.assertFalse(first["active"], combination)
                self.assertTrue(second["active"], combination)
            else:
                self.assertFalse(first["active"], combination)
            self.assertGreaterEqual(display_score(current), 0)
            self.assertLessEqual(display_score(current), 100)
            seen += 1
        self.assertEqual(seen, 1024)

    def test_unknown_coverage_blocks_degraded_and_recovery(self):
        degraded = domains(("degraded", "healthy", "healthy", "healthy", "healthy"))
        self.assertFalse(evaluate_gate(degraded, False, {})["active"])
        healthy = domains(("healthy",) * 5)
        held = evaluate_gate(healthy, False, {"active": True, "recovery_streak": 1})
        self.assertTrue(held["active"])
        self.assertEqual(held["recovery_streak"], 0)

    def test_critical_is_immediate_with_incomplete_coverage(self):
        critical = domains(("healthy", "healthy", "critical", "healthy", "degraded"))
        self.assertTrue(evaluate_gate(critical, False, {})["active"])

    def test_recovery_requires_two_complete_assessments(self):
        healthy = domains(("healthy", "watch", "healthy", "healthy", "healthy"))
        first = evaluate_gate(healthy, True, {"active": True})
        second = evaluate_gate(healthy, True, first)
        self.assertTrue(first["active"])
        self.assertFalse(second["active"])
        self.assertEqual(second["transition"], "recovery")


class IdentityAndTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), "fixtures", "sanitized-real-api-shapes.json"), encoding="utf-8") as fh:
            cls.fixture = json.load(fh)

    def test_sanitized_real_shape_fixture(self):
        completed, pending = self.fixture["pods"]
        self.assertTrue(is_successful_job_pod(completed))
        replica_sets = {("demo", "web-rs"): ("Deployment", "web")}
        self.assertEqual(stable_owner(pending, replica_sets, {})["name"], "web")
        self.assertEqual(event_timestamp(self.fixture["events"][0]).microsecond, 173860)

    def test_replica_churn_collapses_to_one_workload_group(self):
        rs = {("demo", "web-rs"): ("Deployment", "web")}
        keys = set()
        for index in range(50):
            pod = {"metadata": {"namespace": "demo", "name": "web-{}".format(index), "ownerReferences": [{"kind": "ReplicaSet", "name": "web-rs", "controller": True}]}}
            owner = stable_owner(pod, rs, {})
            keys.add(problem_key("worker-a", "demo", owner, "scheduling"))
        self.assertEqual(keys, {"worker-a/demo/Deployment/web/scheduling"})

    def test_twenty_thousand_observations_collapse_to_one_workload_group(self):
        replica_sets = {("demo", "web-rs"): ("Deployment", "web")}
        keys = set()
        for index in range(20000):
            pod = {"metadata": {"namespace": "demo", "name": "web-{}".format(index), "ownerReferences": [{"kind": "ReplicaSet", "name": "web-rs", "controller": True}]}}
            owner = stable_owner(pod, replica_sets, {})
            keys.add(problem_key("worker-a", "demo", owner, "scheduling"))
        self.assertEqual(keys, {"worker-a/demo/Deployment/web/scheduling"})

    def test_unresolved_pods_do_not_merge(self):
        keys = set()
        for name in ("first", "second"):
            pod = {"metadata": {"namespace": "demo", "name": name}}
            keys.add(problem_key("worker-a", "demo", stable_owner(pod, {}, {}), "availability"))
        self.assertEqual(len(keys), 2)

    def test_successful_job_pod_is_not_unavailable(self):
        pod = {"metadata": {"ownerReferences": [{"kind": "Job", "name": "done"}]}, "status": {"phase": "Succeeded"}}
        self.assertTrue(is_successful_job_pod(pod))

    def test_real_fractional_event_timestamp(self):
        event = {"eventTime": "2026-09-15T08:12:13.173860Z", "lastTimestamp": None}
        self.assertEqual(event_timestamp(event).microsecond, 173860)

    def test_series_timestamp_fallback(self):
        event = {"series": {"lastObservedTime": "2026-09-15T08:12:13Z"}}
        self.assertIsNotNone(event_timestamp(event))

    def test_old_and_new_oom_termination_windows(self):
        cutoff = datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)
        recent = self.fixture["pods"][1]["status"]["containerStatuses"][0]["lastState"]["terminated"]
        old = dict(recent, finishedAt="2026-09-15T07:59:59Z")
        self.assertTrue(recent_termination(recent, "OOMKilled", cutoff))
        self.assertFalse(recent_termination(old, "OOMKilled", cutoff))


class AggregationAndConfigTests(unittest.TestCase):
    def test_permission_failure_is_partial_not_healthy_zero(self):
        errors = []

        def denied():
            raise PermissionError("forbidden")

        result = safe_section(errors, "pods", denied)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(errors[0]["source"], "pods")

    def test_kubernetes_list_pagination_is_exhaustive(self):
        api = object.__new__(Api)
        seen = []
        pages = iter((
            {"items": [{"metadata": {"name": "one"}}], "metadata": {"continue": "next/token"}},
            {"items": [{"metadata": {"name": "two"}}], "metadata": {}},
        ))
        api.request = lambda path: seen.append(path) or next(pages)
        items = api.list_items("/api/v1/pods?limit=1")
        self.assertEqual([item["metadata"]["name"] for item in items], ["one", "two"])
        self.assertIn("continue=next%2Ftoken", seen[1])

    def test_rolling_counter_delta_and_reset(self):
        self.assertEqual(counter_delta(8, 5), (3, "complete"))
        self.assertEqual(counter_delta(3, 5), (0, "counter_reset"))
        self.assertEqual(counter_delta(8, None), (0, "first_observation"))

    def test_one_and_two_hundred_of_one_thousand(self):
        def data(unavailable):
            deployments = []
            for index in range(1000):
                ready = 0 if index < unavailable else 1
                deployments.append({"metadata": {"name": "app-{}".format(index)}, "spec": {"replicas": 1}, "status": {"readyReplicas": ready}})
            return {"demo": {"deployments": deployments}}
        self.assertEqual(workload_inventory(data(1))[:2], (1000, 1))
        self.assertEqual(workload_inventory(data(200))[:2], (1000, 200))

    def test_one_thousand_missing_limits_is_one_advisory_aggregate(self):
        pods = [{"spec": {"containers": [{"name": "c{}".format(index), "resources": {}} for index in range(1000)]}}]
        summary = hygiene_summary(pods)
        self.assertEqual(summary["containers_missing_cpu_or_memory_limit"], 1000)
        self.assertEqual(summary["finding_groups"], 1)
        self.assertTrue(summary["advisory_only"])

    def test_absolute_cpu_commit_and_policy_event_rules(self):
        self.assertTrue(node_headroom_watch({"cpu_commit_pct": 93.6, "max_pods_free_pct": None, "pod_cidr_free_pct": None}))
        self.assertNotIn("PolicyViolation", ALLOWED_WARNING_REASONS)
        self.assertEqual(self.fixture_policy_reason(), "PolicyViolation")
        self.assertEqual(self.fixture_policy_count(), 1000)

    @staticmethod
    def fixture_policy_reason():
        path = os.path.join(os.path.dirname(__file__), "fixtures", "sanitized-real-api-shapes.json")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["events"][1]["reason"]

    @staticmethod
    def fixture_policy_count():
        path = os.path.join(os.path.dirname(__file__), "fixtures", "sanitized-real-api-shapes.json")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["events"][1]["count"]

    def test_checksum_ignores_existing_checksum(self):
        document = {"a": 1}
        first = canonical_checksum(document)
        document["checksum"] = "wrong"
        self.assertEqual(first, canonical_checksum(document))

    def test_configuration_is_fail_closed(self):
        base = {"WATCH_NAMESPACES": "demo", "CRITICAL_NAMESPACES": "demo", "POD_PLACEMENT_COVERAGE": "partial", "CLUSTER_ID": "worker-a", "SOURCE_GENERATION": "g1", "CHECK_RESOURCE_SPECS_ENABLED": "false"}
        with patch.dict(os.environ, base, clear=True):
            with self.assertRaisesRegex(ValueError, "DOWNSTREAM_TRIAGE_ENABLED"):
                load_config()
        with patch.dict(os.environ, dict(base, DOWNSTREAM_TRIAGE_ENABLED="flase"), clear=True):
            with self.assertRaisesRegex(ValueError, "exactly true or false"):
                load_config()
        with patch.dict(os.environ, dict(base, DOWNSTREAM_TRIAGE_ENABLED="false", SNAPSHOT_MAX_BYTES="999999"), clear=True):
            with self.assertRaisesRegex(ValueError, "SNAPSHOT_MAX_BYTES"):
                load_config()
        with patch.dict(os.environ, dict(base, DOWNSTREAM_TRIAGE_ENABLED="false", FOX_MESH_MODE="active"), clear=True):
            with self.assertRaisesRegex(ValueError, "FOX_MESH_MODE"):
                load_config()

    def test_fox_pod_churn_is_rekeyed_to_stable_workload_groups(self):
        pods = []
        findings = {}
        for index in range(50):
            name = "web-{}".format(index)
            pods.append({
                "metadata": {
                    "namespace": "demo",
                    "name": name,
                    "ownerReferences": [{"kind": "ReplicaSet", "name": "web-rs", "controller": True}],
                }
            })
            findings["finding-{}".format(index)] = {
                "kind": "Pod",
                "name": name,
                "check": "pod-health",
                "reason": "pending-too-long",
                "classification": "degraded",
                "score": 65,
                "status": "ongoing",
            }
        namespace_data = {
            "demo": {
                "pods": pods,
                "fox_state_status": "complete",
                "fox_state": {"version": 1, "namespace": "demo", "findings": findings},
            }
        }
        summary, normalized, impacts = fox_state_findings(
            namespace_data,
            "worker-a",
            {("demo", "web-rs"): ("Deployment", "web")},
            {},
        )
        self.assertEqual(summary["ongoing_findings"], 50)
        self.assertEqual(summary["stable_groups"], 1)
        self.assertEqual({row["key"] for row in normalized}, {"worker-a/demo/Deployment/web/scheduling"})
        self.assertEqual(impacts["nodes_scheduling"], "degraded")

    def test_fox_mapping_exposes_candidate_impact_without_gate_mutation(self):
        self.assertEqual(fox_symptom_family("log-pattern", "log-panic"), "application_error")
        self.assertEqual(fox_symptom_family("pvc", "lost"), "storage")
        namespace_data = {"demo": {"pods": [], "fox_state_status": "complete", "fox_state": {
            "version": 1,
            "namespace": "demo",
            "findings": {"x": {"kind": "Deployment", "name": "web", "check": "workload", "reason": "ready-replicas-below-desired", "classification": "incident-likely", "score": 85, "status": "ongoing"}},
        }}}
        _, _, impacts = fox_state_findings(namespace_data, "worker-a", {}, {})
        self.assertEqual(impacts, {"workload_availability": "degraded"})

    def test_fox_only_groups_do_not_influence_native_domain_counts(self):
        groups = {
            "fox": {"symptom_family": "scheduling", "source_counts": {"fox": 50}},
            "native": {"symptom_family": "scheduling", "source_counts": {"native": 2, "fox": 1}},
        }
        self.assertEqual(native_group_count(groups, "scheduling"), 1)

    def test_fox_comparison_groups_are_bounded_and_separate(self):
        findings = []
        for index in range(20):
            findings.append({
                "key": "worker/demo/Deployment/app-{}/availability".format(index),
                "namespace": "demo",
                "owner": {"kind": "Deployment", "name": "app-{}".format(index), "resolved": True},
                "symptom_family": "availability",
                "detail": {"finding_id": str(index)},
            })
        rows, truncated = collapse_fox_findings(findings, {findings[0]["key"]}, 5)
        self.assertEqual(len(rows), 5)
        self.assertTrue(truncated)
        self.assertTrue(rows[0]["corroborates_native"])

    def test_malformed_namespace_owned_fox_state_cannot_break_collection(self):
        namespace_data = {"demo": {"pods": [], "fox_state_status": "complete", "fox_state": {
            "version": 1,
            "namespace": "demo",
            "findings": {
                "bad-score": {"kind": "Pod", "name": "web-1", "check": "pod-health", "reason": "not-ready", "classification": "degraded", "score": "not-a-number", "status": "ongoing"},
                "bad-name": {"kind": "Pod", "name": "../../secret", "check": "pod-health", "reason": "not-ready", "classification": "degraded", "score": 80, "status": "ongoing"},
                "not-an-object": "bad",
            },
        }}}
        summary, normalized, impacts = fox_state_findings(namespace_data, "worker-a", {}, {})
        self.assertEqual(summary["invalid_findings"], 3)
        self.assertEqual(normalized, [])
        self.assertEqual(impacts, {})


class CalibrationTests(unittest.TestCase):
    def test_ten_weekdays_produce_twenty_slots_across_dst_weekend(self):
        slots = list(expected_slots(date(2026, 10, 19), date(2026, 10, 30)))
        self.assertEqual(len(slots), 20)
        self.assertEqual(len({name for name, _ in slots}), 20)

    def test_controller_outage_is_recorded_as_missed_after_grace(self):
        rows = audit(
            date(2026, 9, 15),
            date(2026, 9, 15),
            {},
            datetime(2026, 9, 15, 18, 0, tzinfo=LONDON),
        )
        self.assertEqual([row["state"] for row in rows], ["missed", "missed"])

    def test_accelerated_qualification_is_explicitly_not_real_soak(self):
        result = replay()
        self.assertEqual(result["slot_count"], 20)
        self.assertFalse(result["substitutes_for_real_elapsed_soak"])


if __name__ == "__main__":
    unittest.main()
