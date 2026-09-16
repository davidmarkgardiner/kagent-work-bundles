import importlib.util
import os
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("assessor", os.path.join(os.path.dirname(__file__), "assessor.py"))
assessor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assessor)


class AssessorTests(unittest.TestCase):
    def snapshot(self):
        return {
            "cluster_id": "worker-a",
            "source_generation": "g1",
            "snapshot_seq": 7,
            "checksum": "sha256:abc",
            "triage_mode": "report_only",
            "display_score": 65,
            "coverage": {"complete": True},
            "gate": {"active": True},
            "domains": {
                "delivery": {"status": "healthy", "reasons": []},
                "nodes_scheduling": {"status": "degraded", "reasons": ["pending"]},
            },
            "problem_groups": [{"key": "worker-a/demo/Deployment/app/scheduling", "count": 20000, "symptom_family": "scheduling"}],
        }

    def test_output_is_bounded_evidence_only_and_has_no_tools(self):
        result = assessor.build_analysis(self.snapshot())
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["document"]["problem_groups"][0]["count"], 20000)
        self.assertTrue(all(claim["evidence_path"].startswith("/") for claim in result["document"]["claims"]))

    def test_partial_snapshot_is_rejected(self):
        snapshot = self.snapshot()
        snapshot["coverage"]["complete"] = False
        with self.assertRaisesRegex(RuntimeError, "complete"):
            assessor.build_analysis(snapshot)

    def test_model_candidate_can_only_select_supplied_claims(self):
        snapshot = self.snapshot()
        evidence = assessor.build_analysis(snapshot)["document"]
        candidate = {
            "root_layer": "unknown",
            "recommendations": ["Inspect through the approved path."],
            "uncertainties": ["No live lookup."],
            "claim_ids": ["domain-nodes_scheduling", "problem-group-0"],
        }
        result = assessor.validate_model_candidate(candidate, snapshot, evidence)
        self.assertEqual(result["severity"], "warning")
        self.assertEqual([item["id"] for item in result["claims"]], candidate["claim_ids"])

    def test_unsupported_root_layer_and_claim_fail_closed(self):
        snapshot = self.snapshot()
        evidence = assessor.build_analysis(snapshot)["document"]
        base = {"root_layer": "unknown", "recommendations": [], "uncertainties": [], "claim_ids": []}
        with self.assertRaisesRegex(RuntimeError, "root layer"):
            assessor.validate_model_candidate(dict(base, root_layer="application"), snapshot, evidence)
        with self.assertRaisesRegex(RuntimeError, "claim ID"):
            assessor.validate_model_candidate(dict(base, claim_ids=["invented"]), snapshot, evidence)

    def test_model_timeout_preserves_deterministic_assessment(self):
        with patch.dict(os.environ, {"MODEL_CHAT_URL": "https://model.example.invalid"}), \
             patch.object(assessor, "invoke_model", side_effect=TimeoutError("timeout")):
            result = assessor.build_analysis(self.snapshot())
        self.assertEqual(result["mode"], "deterministic_evidence_only")
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["document"]["model_status"], "failed")
        self.assertEqual(result["document"]["model_error"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
