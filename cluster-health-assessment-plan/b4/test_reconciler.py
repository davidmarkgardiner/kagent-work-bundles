import importlib.util
import os
import unittest


SPEC = importlib.util.spec_from_file_location("reconciler", os.path.join(os.path.dirname(__file__), "reconciler.py"))
reconciler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconciler)


class ReconcilerTests(unittest.TestCase):
    def test_one_cluster_summary_contains_no_external_delivery(self):
        analysis = {
            "cluster_id": "worker-a",
            "source_generation": "g1",
            "snapshot_seq": 7,
            "source_checksum": "sha256:abc",
            "mode": "deterministic_evidence_only",
            "document": {
                "score": 65,
                "gate": {"active": True},
                "priorities": [{"domain": "nodes_scheduling"}],
                "problem_groups": [{"key": "worker-a/demo/Deployment/app/scheduling", "count": 20000}],
                "claims": [{"claim": "pending", "evidence_path": "/problem_groups/0"}],
                "limitations": [],
                "model_status": "disabled",
            },
        }
        summary = reconciler.summary_from_analysis(analysis)
        self.assertEqual(summary["cluster_id"], "worker-a")
        self.assertEqual(summary["body"]["external_delivery"], "disabled_lab_ledger")
        self.assertEqual(len(summary["body"]["problem_groups"]), 1)


if __name__ == "__main__":
    unittest.main()
