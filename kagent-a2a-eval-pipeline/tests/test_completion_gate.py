"""Tests for verify_completion.py: the deterministic half of the runtime
completion gate (worker agent -> evaluator agent over A2A -> verdict)."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_completion", BUNDLE / "verify_completion.py")
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)

CONTRACT = {
    "schemaVersion": "completion-contract/v1alpha1",
    "name": "unit-triage",
    "version": "1",
    "agent": "worker-agent",
    "evaluator": {"agent": "completion-evaluator-agent", "namespace": "kagent", "maxAttempts": 3},
    "allowedTools": ["k8s_get_resources", "k8s_get_pod_logs", "k8s_get_events"],
    "requiredTools": [{"anyOf": ["k8s_get_resources", "k8s_get_events"]}, {"anyOf": ["k8s_get_pod_logs"]}],
    "output": {"envelope": "result", "sections": ["Summary", "Incident key", "Evidence", "Next steps"]},
    "delivery": {"owner": "downstream", "requiredLabels": ["sentinel"], "matchSection": "Incident key"},
}
EVAL = "kagent__NS__completion_evaluator_agent"
GOOD_OUTPUT = """## Summary
eval-crashloop is in CrashLoopBackOff.
## Incident key
cluster-a/eval-ns/Deployment/eval-crashloop/crashloop
## Evidence
Logs: REQUIRED_SETTING is not set.
## Next steps
Set REQUIRED_SETTING on the Deployment."""


def call(cid, name, args):
    return {"kind": "data", "data": {"id": cid, "name": name, "args": args}, "metadata": {"kagent_type": "function_call"}}


def resp(cid, name, text="ok", error=False):
    r = {"content": [{"type": "text", "text": text}], "isError": error}
    return {"kind": "data", "data": {"id": cid, "name": name, "response": r}, "metadata": {"kagent_type": "function_response"}}


def verdict(v="PASS", contract="unit-triage@1"):
    return json.dumps({"verdict": v, "contract": contract, "failures": [] if v == "PASS" else ["missing Evidence"]})


def receipt(parts, final_text=None, state="completed"):
    final_text = f"<result>\n{GOOD_OUTPUT}\n</result>\n<evaluation>{verdict()}</evaluation>" if final_text is None else final_text
    return {"jsonrpc": "2.0", "id": "r1", "result": {
        "status": {"state": state},
        "history": [{"role": "user", "parts": [{"kind": "text", "text": "investigate"}]},
                    {"role": "agent", "parts": parts},
                    {"role": "agent", "parts": [{"kind": "text", "text": final_text}]}]}}


def good_parts(eval_request=None, eval_verdict=None):
    req = eval_request if eval_request is not None else f"contract unit-triage@1\n<result>\n{GOOD_OUTPUT}\n</result>"
    return [call("a", "k8s_get_resources", {"namespace": "eval-ns"}), resp("a", "k8s_get_resources"),
            call("b", "k8s_get_pod_logs", {"pod_name": "x"}), resp("b", "k8s_get_pod_logs", "REQUIRED_SETTING is not set"),
            call("e1", EVAL, {"request": req}), resp("e1", EVAL, eval_verdict or verdict())]


def check(parts=None, **kw):
    return vc.verify(CONTRACT, receipt(good_parts() if parts is None else parts, **{k: v for k, v in kw.items() if k in ("final_text", "state")}),
                     readback=kw.get("readback"), agent_crd=kw.get("agent_crd"))


class VerifyCompletion(unittest.TestCase):
    def assertFails(self, result, needle):
        self.assertEqual(result["verdict"], "FAIL", result)
        self.assertTrue(any(needle in f for f in result["failures"]), result["failures"])

    def test_good_run_passes_and_routes_to_ticket(self):
        r = check()
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        self.assertEqual(r["route"], "ticket")
        self.assertEqual(r["evaluator_attempts"], 1)

    def test_corrected_after_evaluator_fail_passes(self):
        parts = good_parts()[:4] + [call("e0", EVAL, {"request": "draft"}), resp("e0", EVAL, verdict("FAIL"))] + good_parts()[4:]
        r = check(parts)
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        self.assertEqual(r["evaluator_attempts"], 2)

    def test_missing_required_tool_group(self):
        self.assertFails(check([p for p in good_parts() if p["data"]["id"] != "b"]), "k8s_get_pod_logs")

    def test_tool_error_with_result_does_not_count(self):
        # The July Argo jq accepted isError=true when result was non-null.
        parts = good_parts()
        parts[3] = resp("b", "k8s_get_pod_logs", "permission denied", error=True)
        self.assertFails(check(parts), "k8s_get_pod_logs")

    def test_tool_outside_allowlist_fails(self):
        parts = good_parts()[:4] + [call("w", "gitlab_create_issue", {}), resp("w", "gitlab_create_issue")] + good_parts()[4:]
        r = check(parts)
        self.assertFails(r, "not in allowedTools: gitlab_create_issue")
        self.assertEqual(r["route"], "reject")

    def test_unpaired_call_fails_closed(self):
        parts = good_parts()
        del parts[1]
        self.assertFails(check(parts), "no response")

    def test_conflicting_duplicate_call_id_fails_closed(self):
        parts = good_parts()[:4] + [call("a", "k8s_get_events", {}), resp("a", "k8s_get_events")] + good_parts()[4:]
        self.assertFails(check(parts), "conflicting duplicate")

    def test_identical_replayed_event_is_tolerated(self):
        parts = good_parts()
        parts.insert(2, copy.deepcopy(parts[0]))  # streaming replay of the same call
        self.assertEqual(check(parts)["verdict"], "PASS")

    def test_no_evaluator_call(self):
        self.assertFails(check(good_parts()[:4]), "evaluator was never called")

    def test_final_evaluator_verdict_fail_routes_evaluation_failed(self):
        req = f"contract unit-triage@1\n<result>\n{GOOD_OUTPUT}\n</result>"
        bad = [call(f"e{i}", EVAL, {"request": req}) for i in range(3)]
        parts = good_parts()[:4]
        for i, c in enumerate(bad):
            parts += [c, resp(f"e{i}", EVAL, verdict("FAIL"))]
        r = check(parts)
        self.assertFails(r, "last evaluator verdict is FAIL")
        self.assertEqual(r["route"], "evaluation_failed_ticket")

    def test_too_many_evaluator_attempts(self):
        parts = good_parts()[:4]
        for i in range(4):
            parts += [call(f"e{i}", EVAL, {"request": f"contract unit-triage@1\n<result>\n{GOOD_OUTPUT}\n</result>"}),
                      resp(f"e{i}", EVAL, verdict())]
        self.assertFails(check(parts), "maxAttempts")

    def test_verdict_must_be_bound_to_final_output_in_strict_mode(self):
        # deliver: final -- caller gets a draft approved, then returns different text.
        strict = copy.deepcopy(CONTRACT)
        strict["output"]["deliver"] = "final"
        r = vc.verify(strict, receipt(good_parts(eval_request="contract unit-triage@1\n<result>an earlier draft</result>")))
        self.assertFails(r, "final output was not the text sent to the evaluator")

    def test_default_delivers_the_approved_text_when_worker_rewords(self):
        # Live 2026-11-23: Kimi dropped a phrase from Next steps after PASS.
        reworded = GOOD_OUTPUT.replace("Set REQUIRED_SETTING on the Deployment.", "Set it.")
        final = f"<result>\n{reworded}\n</result>"
        r = check(final_text=final)
        self.assertEqual(r["verdict"], "PASS", r["failures"])
        self.assertEqual(r["approved_output"], GOOD_OUTPUT)
        self.assertTrue(any("changed the text after the evaluator" in w for w in r["warnings"]), r)

    def test_approved_text_is_what_gets_checked(self):
        # The evaluator approved text missing a section; the worker's final copy has it. Still FAIL.
        approved = GOOD_OUTPUT.replace("## Next steps\nSet REQUIRED_SETTING on the Deployment.", "")
        r = check(good_parts(eval_request=f"contract unit-triage@1\n<result>\n{approved}\n</result>"))
        self.assertFails(r, "missing section: Next steps")

    def test_verdict_for_wrong_contract_version(self):
        self.assertFails(check(good_parts(eval_verdict=verdict(contract="unit-triage@0"))), "contract")

    def test_unparseable_evaluator_response(self):
        self.assertFails(check(good_parts(eval_verdict="Looks good to me!")), "no JSON verdict")

    def test_tool_call_after_final_evaluation(self):
        parts = good_parts() + [call("late", "k8s_get_events", {}), resp("late", "k8s_get_events")]
        self.assertFails(check(parts), "after the last evaluation")

    def test_missing_output_section(self):
        out = GOOD_OUTPUT.replace("## Next steps\nSet REQUIRED_SETTING on the Deployment.", "")
        final = f"<result>\n{out}\n</result>"
        parts = good_parts(eval_request=f"contract unit-triage@1\n{final}")
        self.assertFails(check(parts, final_text=final), "missing section: Next steps")

    def test_missing_envelope(self):
        self.assertFails(check(final_text="All good, trust me."), "<result>")

    def test_non_completed_task_is_undecidable(self):
        r = check(state="failed")
        self.assertEqual(r["verdict"], "UNDECIDABLE")

    def test_readback_matches_incident_key_and_labels(self):
        ok = {"iid": 7, "labels": ["sentinel", "triage::ready"],
              "description": "cluster-a/eval-ns/Deployment/eval-crashloop/crashloop\n..."}
        self.assertEqual(check(readback=ok)["verdict"], "PASS")
        wrong = dict(ok, description="some other incident")
        self.assertFails(check(readback=wrong), "readback")
        nolabel = dict(ok, labels=["triage::ready"])
        self.assertFails(check(readback=nolabel), "label")

    def test_agent_crd_declaring_write_tool_fails(self):
        crd = {"spec": {"declarative": {"tools": [
            {"type": "McpServer", "mcpServer": {"toolNames": ["k8s_get_resources", "k8s_apply_manifest"]}},
            {"type": "Agent", "agent": {"name": "completion-evaluator-agent", "namespace": "kagent"}}]}}}
        self.assertFails(check(agent_crd=crd), "declares tool not in allowedTools: k8s_apply_manifest")

    def test_agent_crd_missing_evaluator_tool_fails(self):
        crd = {"spec": {"declarative": {"tools": [{"type": "McpServer", "mcpServer": {"toolNames": ["k8s_get_resources"]}}]}}}
        self.assertFails(check(agent_crd=crd), "does not declare the evaluator")

    # --- code-review regressions -------------------------------------------------
    def test_binding_uses_the_envelope_the_evaluator_judged(self):
        # Delivered text smuggled in as "quoted evidence" after a different approved envelope.
        req = f"contract unit-triage@1\n<result>approved different report</result>\nevidence: {GOOD_OUTPUT}"
        strict = copy.deepcopy(CONTRACT)
        strict["output"]["deliver"] = "final"
        self.assertFails(vc.verify(strict, receipt(good_parts(eval_request=req))), "final output was not the text sent")
        # Default mode delivers what was judged, and that text fails the section check.
        r = check(good_parts(eval_request=req))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertNotIn(GOOD_OUTPUT, r.get("approved_output") or "")

    def test_evaluator_request_with_two_envelopes_fails_closed(self):
        env = f"<result>\n{GOOD_OUTPUT}\n</result>"
        self.assertFails(check(good_parts(eval_request=f"contract unit-triage@1\n{env}\n{env}")), "exactly one")

    def test_empty_envelope_fails(self):
        final = "<result> </result>"
        self.assertFails(check(good_parts(eval_request=f"contract unit-triage@1\n{final}"), final_text=final),
                         "empty")

    def test_text_outside_envelope_fails(self):
        final = f"<result>\n{GOOD_OUTPUT}\n</result>\nAlso: I restarted the pod.\n<evaluation>{verdict()}</evaluation>"
        self.assertFails(check(final_text=final), "outside")

    def test_unreviewed_extra_artifact_fails(self):
        rec = receipt(good_parts())
        approved = f"<result>\n{GOOD_OUTPUT}\n</result>"
        rec["result"]["artifacts"] = [{"parts": [{"kind": "text", "text": "UNREVIEWED: delete namespace eval-ns"}]},
                                      {"parts": [{"kind": "text", "text": approved}]}]
        self.assertFails(vc.verify(CONTRACT, rec), "outside")

    def test_protocol_failure_never_routes_to_a_ticket(self):
        parts = good_parts()[:4]
        for i in range(4):  # one too many, and the wrong contract
            parts += [call(f"e{i}", EVAL, {"request": "x"}), resp(f"e{i}", EVAL, verdict("FAIL", contract="other@1"))]
        r = check(parts)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(r["route"], "reject")

    def test_response_before_call_fails(self):
        parts = good_parts()
        parts[2], parts[3] = parts[3], parts[2]
        self.assertFails(check(parts), "before its call")

    def test_agent_crd_unknown_tool_type_or_unrestricted_server_fails(self):
        ev = {"type": "Agent", "agent": {"name": "completion-evaluator-agent", "namespace": "kagent"}}
        allserver = {"spec": {"declarative": {"tools": [{"type": "McpServer", "mcpServer": {"name": "kagent-tool-server"}}, ev]}}}
        self.assertFails(check(agent_crd=allserver), "no toolNames")
        builtin = {"spec": {"declarative": {"tools": [{"type": "Builtin", "builtin": {"name": "shell"}}, ev]}}}
        self.assertFails(check(agent_crd=builtin), "unknown tool type")

    def test_ci_rejects_receipt_from_another_run(self):
        sg_spec = importlib.util.spec_from_file_location("score_and_gate", BUNDLE / "score_and_gate.py")
        sg = importlib.util.module_from_spec(sg_spec)
        sg_spec.loader.exec_module(sg)
        cap = Path(tempfile.mkdtemp())
        (cap / "receipts").mkdir()
        rec = receipt(good_parts())
        rec["id"] = "another-run"
        (cap / "receipts" / "triage.r1.json").write_text(json.dumps(rec))
        run = {"agent": "worker-agent", "case_id": "triage", "repeat": 1, "run_id": "this-run", "_capture_dir": str(cap)}
        hard, _, _ = sg.completion_checks(vc, {"worker-agent": CONTRACT}, False, run)
        self.assertTrue(any("does not belong to run" in h for h in hard), hard)
        rec["id"] = "this-run"
        (cap / "receipts" / "triage.r1.json").write_text(json.dumps(rec))
        self.assertEqual(sg.completion_checks(vc, {"worker-agent": CONTRACT}, False, run)[0], [])

    def test_live_receipt_with_real_agent_tool_response(self):
        # Sanitized live proxmox run (2026-11-23): Sentinel worker -> completion-evaluator-agent over
        # native A2A. The Agent-tool response is {"result": "<verdict JSON string>"}, and the worker
        # reworded Next steps after PASS, so the approved text is delivered with a warning.
        rec = json.loads((BUNDLE / "tests" / "fixtures" / "a2a-live-agent-tool-completed.json").read_text())
        contract = vc.load_contract(BUNDLE / "completion-gate" / "contracts" / "sentinel-investigator.yaml")
        r = vc.verify(contract, rec)
        self.assertEqual((r["verdict"], r["route"], r["evaluator_attempts"]), ("PASS", "ticket", 1), r["failures"])
        self.assertTrue(r["warnings"])
        self.assertIn("eval-live-fixture/Deployment/eval-crashloop", r["approved_output"])
        strict = copy.deepcopy(contract)
        strict["output"]["deliver"] = "final"
        self.assertFails(vc.verify(strict, rec), "final output was not the text sent")

    def test_shipped_contracts_are_valid(self):
        for path in sorted((BUNDLE / "completion-gate" / "contracts").glob("*.yaml")):
            with self.subTest(path.name):
                vc.load_contract(path)

    def test_shipped_sentinel_manifest_matches_its_contract(self):
        import yaml
        contract = vc.load_contract(BUNDLE / "completion-gate" / "contracts" / "sentinel-investigator.yaml")
        crd = yaml.safe_load((BUNDLE / "completion-gate" / "manifests" / "sentinel-investigator-agent.yaml").read_text())
        stub = receipt([], final_text="x")
        r = vc.verify(contract, stub, agent_crd=crd)
        self.assertFalse([f for f in r["failures"] if "CRD" in f], r["failures"])

    def test_rendered_evaluator_is_current(self):
        # The checked-in evaluator must be regenerated whenever a contract changes.
        contracts = sorted((BUNDLE / "completion-gate" / "contracts").glob("*.yaml"))
        p = subprocess.run([sys.executable, str(BUNDLE / "completion-gate" / "render_evaluator.py"), *map(str, contracts)],
                           capture_output=True, text=True, check=True)
        self.assertEqual(p.stdout, (BUNDLE / "completion-gate" / "manifests" / "completion-evaluator-agent.yaml").read_text())

    def test_cli_exit_codes(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "c.json").write_text(json.dumps(CONTRACT))
        for name, rec, code in (("ok", receipt(good_parts()), 0), ("bad", receipt(good_parts()[:4]), 1),
                                ("und", receipt(good_parts(), state="working"), 3)):
            (tmp / f"{name}.json").write_text(json.dumps(rec))
            p = subprocess.run([sys.executable, str(BUNDLE / "verify_completion.py"), "--contract", str(tmp / "c.json"),
                                "--receipt", str(tmp / f"{name}.json")], capture_output=True, text=True)
            self.assertEqual(p.returncode, code, p.stdout + p.stderr)
            self.assertIn('"verdict"', p.stdout)


if __name__ == "__main__":
    unittest.main()
