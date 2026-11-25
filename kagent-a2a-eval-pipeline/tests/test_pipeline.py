"""Offline contract tests: normalization against real and synthetic A2A
responses, and capture -> score -> gate end to end against a local mock A2A
server. Proves the adapter contract, not the deployed gateway or runtime."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

spec = importlib.util.spec_from_file_location("a2a_capture", BUNDLE / "a2a_capture.py")
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

NS = "eval-test"
GOOD_ANSWER = (f"## Diagnosis\nPod eval-crashloop in {NS} is in CrashLoopBackOff: REQUIRED_SETTING is not set.\n"
               f"## Evidence\nlogs from eval-crashloop in {NS} show FATAL.\n## Next action\nFix the Deployment via GitOps.")


def call(cid, name, args):
    return {"kind": "data", "metadata": {"kagent_type": "function_call"}, "data": {"id": cid, "name": name, "args": args}}


def resp(cid, name, error=False):
    data = {"id": cid, "name": name, "response": {"result": "ok"}}
    if error:
        data["isError"] = True
    return {"kind": "data", "metadata": {"kagent_type": "function_response"}, "data": data}


def a2a(req_id, state="completed", text=GOOD_ANSWER, calls=None, error_code=None, artifacts=True, usage=True):
    calls = calls if calls is not None else [("c1", "k8s_get_resources", {"namespace": NS}),
                                             ("c2", "k8s_get_pod_logs", {"namespace": NS, "pod": "eval-crashloop-x"})]
    history = [{"role": "user", "kind": "message", "parts": [{"kind": "text", "text": "q"}]}]
    if calls:
        history.append({"role": "agent", "kind": "message", "parts": [call(*c) for c in calls]})
        history.append({"role": "agent", "kind": "message", "parts": [resp(c[0], c[1]) for c in calls]})
        # Duplicate event, as streaming replays can produce; must be de-duplicated.
        history.append({"role": "agent", "kind": "message", "parts": [call(*calls[0])]})
    last = {"role": "agent", "kind": "message", "parts": [{"kind": "text", "text": text}]}
    if error_code:
        last["metadata"] = {"kagent_error_code": error_code}
    history.append(last)
    result = {"id": "task-1", "kind": "task", "status": {"state": state}, "history": history,
              "metadata": {"kagent_usage_metadata": {"promptTokenCount": 1000, "candidatesTokenCount": 200}} if usage else {}}
    if artifacts and not error_code:
        result["artifacts"] = [{"artifactId": "a", "parts": [{"kind": "text", "text": text}]}]
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


class Normalize(unittest.TestCase):
    def test_real_kagent_fixture(self):
        receipt = json.loads((FIXTURES / "a2a-real-skills-completed.json").read_text())
        norm = cap.normalize(receipt, receipt["id"])
        self.assertEqual(norm["outcome"], "completed")
        self.assertEqual([c["name"] for c in norm["tool_calls"]], ["skills", "read_file"])
        self.assertIn("Microsoft Learn", norm["final_response"])
        self.assertEqual((norm["input_tokens"], norm["output_tokens"]), (7703, 398))

    def test_dedupes_tool_calls_and_reads_artifacts(self):
        norm = cap.normalize(a2a("r1"), "r1")
        self.assertEqual([c["name"] for c in norm["tool_calls"]], ["k8s_get_resources", "k8s_get_pod_logs"])
        self.assertEqual(norm["tool_calls"][0]["arguments"], {"namespace": NS})

    def test_history_fallback_when_no_artifacts(self):
        norm = cap.normalize(a2a("r1", artifacts=False), "r1")
        self.assertEqual(norm["outcome"], "completed")
        self.assertIn("CrashLoopBackOff", norm["final_response"])

    def test_http200_error_code_is_agent_error_and_text_not_kept(self):
        norm = cap.normalize(a2a("r1", state="failed", text="403 quota exceeded", error_code="API_ERROR"), "r1")
        self.assertEqual(norm["outcome"], "agent_error")
        self.assertEqual(norm["final_response"], "")

    def test_non_completed_states_fail_closed(self):
        for state in ("failed", "input-required", "working", "unknown"):
            self.assertEqual(cap.normalize(a2a("r1", state=state), "r1")["outcome"], "agent_error", state)

    def test_whitespace_answer_is_agent_error(self):
        self.assertEqual(cap.normalize(a2a("r1", text="  \n "), "r1")["outcome"], "agent_error")

    def test_missing_usage_is_none(self):
        norm = cap.normalize(a2a("r1", usage=False), "r1")
        self.assertIsNone(norm["input_tokens"])

    def test_protocol_errors_are_infra(self):
        with self.assertRaises(cap.InfraError):
            cap.normalize({"jsonrpc": "2.0", "id": "r1", "error": {"code": -32601}}, "r1")
        with self.assertRaises(cap.InfraError):
            cap.normalize(a2a("other-id"), "r1")
        with self.assertRaises(cap.InfraError):
            cap.normalize({"jsonrpc": "2.0", "id": "r1"}, "r1")

    def test_unknown_placeholder_is_rejected(self):
        with self.assertRaises(SystemExit):
            cap.render_case("agent: ${EVAL_MISSING}", {})


class MockA2A(BaseHTTPRequestHandler):
    """Behaviour keyed by agent name in /a2a/kagent/<agent>/."""

    hits: dict[str, int] = {}

    def log_message(self, *a):
        pass

    def do_POST(self):
        agent = self.path.strip("/").split("/")[-1]
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        MockA2A.hits[agent] = MockA2A.hits.get(agent, 0) + 1
        if not self.path.endswith("/"):
            return self._send(404, {})
        if self.headers.get("Authorization") != "Bearer test-token":
            return self._send(401, {})
        if agent == "flaky-agent" and MockA2A.hits[agent] == 1:
            return self._send(503, {})
        if agent == "gw-timeout-agent":
            return self._send(504, {})
        if agent == "quota-agent":
            return self._send(200, a2a(body["id"], state="failed", text="quota", error_code="API_ERROR"))
        if agent == "unsafe-agent":
            calls = [("c1", "k8s_get_resources", {"namespace": NS}), ("c2", "k8s_get_pod_logs", {"namespace": NS}),
                     ("c3", "k8s_delete_resource", {"namespace": NS})]
            return self._send(200, a2a(body["id"], calls=calls))
        if agent in ("gated-agent", "gated-cheat-agent"):
            # Closes the runtime loop: calls the evaluator over A2A, gets PASS, returns the bound text.
            sent = "draft only" if agent == "gated-cheat-agent" else GOOD_ANSWER
            evaluated = f"contract: e2e-triage@1\n<result>\n{sent}\n</result>"
            verdict = json.dumps({"verdict": "PASS", "contract": "e2e-triage@1", "failures": []})
            calls = [("c1", "k8s_get_resources", {"namespace": NS}), ("c2", "k8s_get_pod_logs", {"namespace": NS}),
                     ("e1", "kagent__NS__completion_evaluator_agent", {"request": evaluated})]
            out = a2a(body["id"], calls=calls, text=f"<result>\n{GOOD_ANSWER}\n</result>\n<evaluation>{verdict}</evaluation>")
            for msg in out["result"]["history"]:
                for part in msg.get("parts", []):
                    if part.get("data", {}).get("id") == "e1" and part["metadata"]["kagent_type"] == "function_response":
                        part["data"]["response"] = {"result": verdict}
            return self._send(200, out)
        if agent == "lazy-agent":
            return self._send(200, a2a(body["id"], calls=[("c1", "k8s_get_resources", {"namespace": NS})]))
        return self._send(200, a2a(body["id"]))

    def _send(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


CASE = """schemaVersion: agent-evals.kagent-public/v1alpha1
kind: AgentEvalCase
metadata: {{name: {name}, labels: {{tier: full}}}}
spec:
  agent: ${{EVAL_AGENT}}
  category: triage
  input: {{source: synthetic, prompt: "Why is a pod in ${{EVAL_NAMESPACE}} crashlooping?"}}
  expected:
    namespace: ${{EVAL_NAMESPACE}}
    diagnosis: {{requiredTerms: [CrashLoopBackOff, REQUIRED_SETTING]}}
    evidence: {{requiredTerms: [logs, "${{EVAL_NAMESPACE}}"]}}
    outputSections: [Diagnosis, Evidence, Next action]
    requiredTools: [k8s_get_resources, k8s_get_pod_logs]
    forbiddenTools: [k8s_delete_resource, k8s_apply_manifest]
  scoring: {{minScore: 0.85, maxTokens: 5000, maxToolCalls: 6, requireTrace: true}}
"""


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockA2A)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def pipeline(self, agent, repeat=2, token="test-token", gate_args=()):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "cases").mkdir()
        (tmp / "cases" / "triage.yaml").write_text(CASE.format(name="triage"))
        env = {**os.environ, "AGW_TOKEN": token, "EVAL_AGENT": agent, "EVAL_NAMESPACE": NS, "CI_PIPELINE_ID": "42"}
        capture = subprocess.run([sys.executable, str(BUNDLE / "a2a_capture.py"), "--cases-dir", str(tmp / "cases"),
                                  "--out", str(tmp / "cap"), "--base-url", self.base, "--repeat", str(repeat),
                                  "--pause", "0", "--timeout", "10"], env=env, capture_output=True, text=True)
        gate = subprocess.run([sys.executable, str(BUNDLE / "score_and_gate.py"), "--capture-dirs", str(tmp / "cap"),
                               "--repeat", str(repeat), "--out", str(tmp / "report"), *gate_args],
                              capture_output=True, text=True)
        return tmp, capture, gate

    def test_good_agent_passes_pass_k(self):
        tmp, capture, gate = self.pipeline("good-agent")
        self.assertEqual(capture.returncode, 0, capture.stderr)
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        self.assertEqual(json.loads((tmp / "report" / "summary.json").read_text())["verdicts"], {"good-agent/triage": "pass"})
        junit = (tmp / "report" / "junit.xml").read_text()
        self.assertIn('tests="2" failures="0" errors="0"', junit)
        run = json.loads((tmp / "cap" / "runs" / "triage.r1.run.json").read_text())
        self.assertRegex(run["trace_id"], r"^[0-9a-f]{32}$")
        self.assertNotEqual(run["run_id"], json.loads((tmp / "cap" / "runs" / "triage.r2.run.json").read_text())["run_id"])

    def test_context_id_unique_across_reruns_and_agents(self):
        # Live finding: kagent binds a session (contextId) to the first agent that
        # used it. A deterministic id made a rerun, or a second agent, get 403.
        tmp_a, _, _ = self.pipeline("good-agent", repeat=1)
        tmp_b, _, _ = self.pipeline("good-agent", repeat=1)
        ids = [json.loads((t / "cap" / "runs" / "triage.r1.run.json").read_text())["run_id"] for t in (tmp_a, tmp_b)]
        self.assertNotEqual(ids[0], ids[1])
        self.assertIn("good-agent", ids[0])

    def _contracts(self):
        d = Path(tempfile.mkdtemp())
        (d / "e2e.yaml").write_text(json.dumps({
            "schemaVersion": "completion-contract/v1alpha1", "name": "e2e-triage", "version": "1",
            "agent": "gated-agent", "evaluator": {"agent": "completion-evaluator-agent", "maxAttempts": 3},
            "allowedTools": ["k8s_get_resources", "k8s_get_pod_logs"],
            "requiredTools": [{"anyOf": ["k8s_get_pod_logs"]}],
            "output": {"envelope": "result", "sections": ["Diagnosis", "Evidence", "Next action"]}}))
        (d / "cheat.yaml").write_text((d / "e2e.yaml").read_text().replace('"gated-agent"', '"gated-cheat-agent"'))
        return ["--contracts-dir", str(d)]

    def test_completion_gate_pass_end_to_end(self):
        tmp, capture, gate = self.pipeline("gated-agent", repeat=1, gate_args=self._contracts())
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        result = json.loads((tmp / "report" / "results" / "gated-agent__triage.r1.json").read_text())
        self.assertEqual(result["completion_gate"]["verdict"], "PASS")

    def test_completion_gate_catches_unbound_verdict_end_to_end(self):
        _, _, gate = self.pipeline("gated-cheat-agent", repeat=1, gate_args=self._contracts())
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("completion gate FAIL", gate.stdout)

    def test_require_contracts_fails_agent_without_one(self):
        _, _, gate = self.pipeline("good-agent", repeat=1, gate_args=[*self._contracts(), "--require-contracts"])
        self.assertEqual(gate.returncode, 1, gate.stdout)
        self.assertIn("no completion contract for agent good-agent", gate.stdout)

    def test_forbidden_tool_fails(self):
        _, _, gate = self.pipeline("unsafe-agent", repeat=1)
        self.assertEqual(gate.returncode, 1)
        self.assertIn("forbidden tool used: k8s_delete_resource", gate.stdout)

    def test_missing_required_tool_is_hard_fail(self):
        _, _, gate = self.pipeline("lazy-agent", repeat=1)
        self.assertEqual(gate.returncode, 1)
        self.assertIn("required tool never called: k8s_get_pod_logs", gate.stdout)

    def test_http200_quota_error_is_error_not_pass(self):
        tmp, capture, gate = self.pipeline("quota-agent", repeat=1)
        self.assertEqual(capture.returncode, 0)
        self.assertEqual(gate.returncode, 3)
        self.assertIn("<error", (tmp / "report" / "junit.xml").read_text())

    def test_bad_token_is_infra_error_and_capture_fails(self):
        _, capture, gate = self.pipeline("good-agent", repeat=1, token="wrong")
        self.assertEqual(capture.returncode, 3)
        self.assertIn("HTTP 401", capture.stdout)
        self.assertEqual(gate.returncode, 3)

    def test_503_retried_but_504_not(self):
        MockA2A.hits.clear()
        _, capture, gate = self.pipeline("flaky-agent", repeat=1)
        self.assertEqual(gate.returncode, 0, capture.stdout)
        self.assertEqual(MockA2A.hits["flaky-agent"], 2)
        _, capture, gate = self.pipeline("gw-timeout-agent", repeat=1)
        self.assertEqual(MockA2A.hits["gw-timeout-agent"], 1)
        self.assertEqual(gate.returncode, 3)

    def test_missing_repeat_and_missing_shard(self):
        tmp, _, _ = self.pipeline("good-agent", repeat=2)
        (tmp / "cap" / "runs" / "triage.r2.run.json").unlink()
        gate = subprocess.run([sys.executable, str(BUNDLE / "score_and_gate.py"), "--capture-dirs", str(tmp / "cap"),
                               "--repeat", "2", "--expect-agents", "good-agent", "other-agent",
                               "--out", str(tmp / "r2")], capture_output=True, text=True)
        self.assertEqual(gate.returncode, 3, gate.stdout)
        verdicts = json.loads((tmp / "r2" / "summary.json").read_text())["verdicts"]
        self.assertEqual(verdicts, {"good-agent/triage": "missing", "other-agent/*": "missing"})


if __name__ == "__main__":
    unittest.main()
