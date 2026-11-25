"""verify_completion.py on kagent 1.x (A2A 1.0) receipts, where the evaluator is a
`subAgent` reached by an ADK `transfer_to_agent` handoff, tool events live in task
artifacts, and the evaluator's verdict is the turn's final text."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_completion", BUNDLE / "verify_completion.py")
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)

FIXTURE = json.loads((BUNDLE / "tests" / "fixtures" / "a2a-v1x-subagent-completed.json").read_text())
CONTRACT = vc.load_contract(BUNDLE / "completion-gate" / "contracts" / "sentinel-investigator.yaml")
PT = "kagent.dev/a2a/part-type"


def arts(rec):
    return rec["result"]["task"]["artifacts"]


def find(rec, pred):
    for i, a in enumerate(arts(rec)):
        for j, p in enumerate(a["parts"]):
            if pred(p):
                return i, j
    raise AssertionError("part not found")


class V1x(unittest.TestCase):
    def assertFails(self, r, needle):
        self.assertEqual(r["verdict"], "FAIL", r)
        self.assertTrue(any(needle in f for f in r["failures"]), r["failures"])

    def test_live_receipt_passes(self):
        r = vc.verify(CONTRACT, FIXTURE)
        self.assertEqual((r["verdict"], r["route"], r["evaluator_attempts"]), ("PASS", "ticket", 1), r["failures"])
        self.assertEqual(r["protocol"], "a2a-1.0")
        self.assertIn("eval-live-fixture/Deployment/eval-crashloop", r["approved_output"])
        self.assertTrue({"k8s_get_resources", "k8s_get_pod_logs"} <= set(r["tools_succeeded"]))

    def test_no_handoff_to_evaluator(self):
        rec = copy.deepcopy(FIXTURE)
        i, j = find(rec, lambda p: (p.get("data") or {}).get("name") == "transfer_to_agent" and (p.get("metadata") or {}).get(PT) == "function_call")
        rec["result"]["task"]["artifacts"][i]["parts"][j]["data"]["args"]["agent_name"] = "someone-else"
        r = vc.verify(CONTRACT, rec)
        self.assertFails(r, "evaluator was never called")
        self.assertFails(r, "not in allowedAgents: someone-else")

    def test_evaluator_verdict_fail(self):
        rec = copy.deepcopy(FIXTURE)
        i, j = find(rec, lambda p: '"verdict"' in p.get("text", ""))
        rec["result"]["task"]["artifacts"][i]["parts"][j]["text"] = json.dumps(
            {"verdict": "FAIL", "contract": "sentinel-investigation@1", "failures": ["Evidence not backed"]})
        self.assertFails(vc.verify(CONTRACT, rec), "last evaluator verdict is FAIL")

    def test_wrong_contract_echo(self):
        rec = copy.deepcopy(FIXTURE)
        i, j = find(rec, lambda p: '"verdict"' in p.get("text", ""))
        p = rec["result"]["task"]["artifacts"][i]["parts"][j]
        p["text"] = p["text"].replace("sentinel-investigation@1", "sentinel-investigation@0")
        self.assertFails(vc.verify(CONTRACT, rec), "evaluator judged contract")

    def test_tool_call_after_handoff(self):
        rec = copy.deepcopy(FIXTURE)
        late = [{"data": {"id": "late1", "name": "k8s_get_events", "args": {}}, "metadata": {PT: "function_call"}},
                {"data": {"id": "late1", "name": "k8s_get_events", "response": {"output": {"output": "x"}}}, "metadata": {PT: "function_response"}}]
        rec["result"]["task"]["artifacts"].append({"artifactId": "late", "parts": late})
        self.assertFails(vc.verify(CONTRACT, rec), "after the last evaluation")

    def test_tool_outside_allowlist(self):
        rec = copy.deepcopy(FIXTURE)
        i, j = find(rec, lambda p: (p.get("data") or {}).get("name") == "k8s_get_events")
        for a in rec["result"]["task"]["artifacts"]:
            for p in a["parts"]:
                if (p.get("data") or {}).get("name") == "k8s_get_events":
                    p["data"]["name"] = "k8s_delete_resource"
        r = vc.verify(CONTRACT, rec)
        self.assertFails(r, "not in allowedTools: k8s_delete_resource")
        self.assertEqual(r["route"], "reject")

    def test_two_envelopes_before_handoff_fail_closed(self):
        rec = copy.deepcopy(FIXTURE)
        i, j = find(rec, lambda p: p.get("text", "").startswith("<result>"))
        p = rec["result"]["task"]["artifacts"][i]["parts"][j]
        p["text"] = "<result>draft</result>\n" + p["text"]
        self.assertFails(vc.verify(CONTRACT, rec), "exactly one <result>")

    def test_not_completed_is_undecidable(self):
        rec = copy.deepcopy(FIXTURE)
        rec["result"]["task"]["status"]["state"] = "TASK_STATE_FAILED"
        self.assertEqual(vc.verify(CONTRACT, rec)["verdict"], "UNDECIDABLE")

    def test_v1alpha3_agent_crd_check(self):
        crd = {"apiVersion": "api.kagent.dev/v1alpha3", "kind": "Agent", "spec": {"template": {"inline": {"tools": [
            {"mcp": {"server": {"name": "kagent-tools-readonly"}, "tools": ["k8s_get_resources", "k8s_get_pod_logs"]}},
            {"subAgent": {"name": "completion-evaluator", "templateRef": {"name": "completion-evaluator"}}}]}}}}
        self.assertEqual(vc.verify(CONTRACT, FIXTURE, agent_crd=crd)["verdict"], "PASS")
        bad = copy.deepcopy(crd)
        bad["spec"]["template"]["inline"]["tools"][0]["mcp"]["tools"].append("k8s_apply_manifest")
        self.assertFails(vc.verify(CONTRACT, FIXTURE, agent_crd=bad), "declares tool not in allowedTools: k8s_apply_manifest")
        noeval = copy.deepcopy(crd)
        noeval["spec"]["template"]["inline"]["tools"].pop()
        self.assertFails(vc.verify(CONTRACT, FIXTURE, agent_crd=noeval), "does not declare the evaluator")
        unrestricted = copy.deepcopy(crd)
        del unrestricted["spec"]["template"]["inline"]["tools"][0]["mcp"]["tools"]
        self.assertFails(vc.verify(CONTRACT, FIXTURE, agent_crd=unrestricted), "no tool list")


if __name__ == "__main__":
    unittest.main()
