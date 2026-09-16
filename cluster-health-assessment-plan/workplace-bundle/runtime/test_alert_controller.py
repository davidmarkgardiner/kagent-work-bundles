import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import alert_controller as controller


NOW = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)


def snapshot(active=True, seq=7, score=70):
    return {
        "cluster_id": "worker-a",
        "source_generation": "generation-1",
        "snapshot_seq": seq,
        "completed_at": (NOW - timedelta(seconds=30)).isoformat().replace("+00:00", "Z"),
        "checksum": "sha256:" + "a" * 64,
        "policy_version": "policy-v1",
        "display_score": score,
        "gate": {"active": active, "reason": "degraded domain persisted"},
        "coverage": {"complete": True},
        "domains": {
            "nodes_scheduling": {"status": "critical", "reasons": ["node unavailable"]},
            "workload_availability": {"status": "degraded", "reasons": ["workload unavailable"]},
            "shared_services": {"status": "healthy", "reasons": []},
            "resource_pressure": {"status": "watch", "reasons": []},
            "delivery": {"status": "healthy", "reasons": []},
        },
        "problem_group_total": 2,
        "problem_groups_truncated": False,
        "problem_groups": [
            {
                "namespace": "payments",
                "owner": {"kind": "Deployment", "name": "api", "resolved": True},
                "symptom_family": "scheduling",
                "count": 50,
                "source_counts": {"native": 50, "fox": 50},
                "examples": [{"pod": "must-not-leak", "message": "raw log must not leak"}],
            },
            {
                "namespace": "catalogue",
                "owner": {"kind": "StatefulSet", "name": "db", "resolved": True},
                "symptom_family": "availability",
                "count": 2,
                "source_counts": {"native": 2},
            },
        ],
    }


class AlertContractTests(unittest.TestCase):
    def test_breach_emits_one_bounded_summary_without_raw_examples(self):
        doc = snapshot()
        event, state = controller.build_event(
            doc, {"snapshot": "cluster-health-snapshot-0000000007"}, {},
            now=NOW, daily_slot="2026-09-16", top_n=10, cluster_ref="worker-a-ref",
        )
        self.assertEqual(event["schema_version"], "cluster-health.alert.v1")
        self.assertEqual(event["action"], "investigate")
        self.assertFalse(event["automation_allowed"])
        self.assertRegex(event["dispatch"]["workflow_name"], r"^cluster-health-investigation-[0-9a-f]{20}$")
        self.assertEqual(event["scope"]["namespaces"], ["catalogue", "payments"])
        self.assertEqual(event["scope"]["top_problem_groups"][0]["count"], 50)
        encoded = json.dumps(event)
        self.assertNotIn("must-not-leak", encoded)
        self.assertNotIn("raw log", encoded)
        self.assertTrue(state["active"])

    def test_no_repeat_within_daily_slot(self):
        doc = snapshot(seq=8)
        previous = {
            "active": True,
            "episode_id": "episode-a",
            "last_daily_slot": "2026-09-16",
        }
        event, state = controller.build_event(
            doc, {"snapshot": "snapshot-8"}, previous,
            now=NOW, daily_slot="2026-09-16", top_n=10, cluster_ref="worker-a-ref",
        )
        self.assertIsNone(event)
        self.assertEqual(state["episode_id"], "episode-a")

    def test_next_day_active_and_healthy_summary(self):
        previous = {
            "active": True,
            "episode_id": "episode-a",
            "last_daily_slot": "2026-09-15",
        }
        daily_alert, daily_state = controller.build_event(
            snapshot(seq=9), {"snapshot": "snapshot-9"}, previous,
            now=NOW, daily_slot="2026-09-16", top_n=10, cluster_ref="worker-a-ref",
        )
        self.assertEqual(daily_alert["action"], "investigate")
        self.assertEqual(daily_alert["dedupe_key"], "cluster-health/worker-a/daily/2026-09-16")
        recovered = snapshot(active=False, seq=10, score=100)
        for domain in recovered["domains"].values():
            domain["status"] = "healthy"
            domain["reasons"] = []
        recovery, state = controller.build_event(
            recovered, {"snapshot": "snapshot-10"}, daily_state,
            now=NOW + timedelta(days=1), daily_slot="2026-09-17",
            top_n=10, cluster_ref="worker-a-ref",
        )
        self.assertEqual(recovery["action"], "healthy")
        self.assertEqual(recovery["health"]["severity"], "healthy")
        self.assertEqual(recovery["dedupe_key"], "cluster-health/worker-a/daily/2026-09-17")
        self.assertFalse(state["active"])
        self.assertEqual(state["episode_id"], "")

    def test_daily_slot_starts_only_after_configured_utc_time(self):
        before = NOW.replace(hour=7, minute=29)
        after = NOW.replace(hour=7, minute=30)
        self.assertIsNone(controller.eligible_daily_slot(before, 7, 30))
        self.assertEqual(controller.eligible_daily_slot(after, 7, 30), "2026-09-16")

    def test_snapshot_identity_and_freshness_fail_closed(self):
        doc = snapshot()
        with self.assertRaisesRegex(ValueError, "cluster_id"):
            controller.validate_snapshot(doc, cluster_id="wrong", generation="generation-1", max_age_seconds=900, now=NOW)
        stale = snapshot()
        stale["completed_at"] = (NOW - timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "freshness"):
            controller.validate_snapshot(stale, cluster_id="worker-a", generation="generation-1", max_age_seconds=900, now=NOW)

    def test_event_id_is_deterministic_and_output_is_size_bounded(self):
        args = dict(now=NOW, daily_slot="2026-09-16", top_n=1, cluster_ref="worker-a-ref")
        first, _ = controller.build_event(snapshot(), {"snapshot": "snapshot-7"}, {}, **args)
        second, _ = controller.build_event(snapshot(), {"snapshot": "snapshot-7"}, {}, **args)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["dispatch"]["workflow_name"], second["dispatch"]["workflow_name"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.ndjson"
            written = controller.append_event(path, first, 65536)
            self.assertEqual(written, path.stat().st_size)
            self.assertEqual(json.loads(path.read_text()), first)
            with self.assertRaisesRegex(ValueError, "byte limit"):
                controller.append_event(path, first, 10)


if __name__ == "__main__":
    unittest.main()
