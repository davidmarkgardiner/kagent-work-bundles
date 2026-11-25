"""a2a_capture --protocol 1x: payload, parsing and fail-closed behaviour, replayed on real kagent 1.x receipts."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B))
spec = importlib.util.spec_from_file_location("a2a_capture", B / "a2a_capture.py")
cap = importlib.util.module_from_spec(spec); spec.loader.exec_module(cap)
FX = B / "tests/fixtures"


def rec(name, rid=None):
    d = json.loads((FX / name).read_text())
    if rid:
        d["id"] = rid
    return d


class Capture1x(unittest.TestCase):
    def test_payload_shape(self):
        p = cap.build_payload_1x("hi", "rid-1")
        m = p["params"]["message"]
        self.assertEqual((p["method"], m["role"], m["parts"]), ("SendMessage", "ROLE_USER", [{"text": "hi"}]))
        self.assertNotIn("contextId", m)  # 1.x binds a contextId to the first agent

    def test_live_healthy_run_is_completed_with_tools_args_and_tokens(self):
        n = cap.normalize_1x(rec("a2a-v1x-demo-healthy-live.json", "x"), "x")
        self.assertEqual((n["outcome"], n["a2a_state"]), ("completed", "completed"))
        self.assertEqual([t["name"] for t in n["tool_calls"]], ["k8s_get_resources"])
        self.assertIsInstance(n["tool_calls"][0]["arguments"], dict)
        self.assertGreater(n["input_tokens"], 0)
        self.assertIn("model-stub", n["final_response"])

    def test_live_failed_run_is_an_agent_error_not_a_pass(self):
        d = rec("a2a-v1x-demo-healthy-live.json", "x")
        d["result"]["task"]["status"]["state"] = "TASK_STATE_FAILED"
        n = cap.normalize_1x(d, "x")
        self.assertEqual(n["outcome"], "agent_error")
        self.assertEqual(n["final_response"], "")

    def test_empty_answer_and_id_mismatch_and_jsonrpc_error_fail_closed(self):
        d = rec("a2a-v1x-demo-healthy-live.json", "x")
        for a in d["result"]["task"]["artifacts"]:
            a["parts"] = [p for p in a["parts"] if "text" not in p]
        self.assertEqual(cap.normalize_1x(d, "x")["outcome_reason"], "empty answer")
        with self.assertRaises(cap.InfraError):
            cap.normalize_1x(rec("a2a-v1x-demo-healthy-live.json", "y"), "x")
        with self.assertRaises(cap.InfraError):
            cap.normalize_1x({"jsonrpc": "2.0", "id": "x", "error": {"code": -32004}}, "x")

    def test_rogue_run_exposes_the_forbidden_tool_to_the_scorer(self):
        n = cap.normalize_1x(rec("a2a-v1x-demo-rogue-delete-live.json", "x"), "x")
        self.assertIn("k8s_delete_resource", [t["name"] for t in n["tool_calls"]])

    def test_default_protocol_and_url_unchanged(self):
        self.assertEqual(cap.DEFAULT_URL_TEMPLATE, "{base}/a2a/{agent_ns}/{agent}/")
        self.assertEqual(cap.URL_TEMPLATE_1X, "{base}/agents/{agent_ns}/{agent}")


if __name__ == "__main__":
    unittest.main()


class DemoCasesAndScene(unittest.TestCase):
    def test_demo_cases_lint_and_scene_is_wired(self):
        import subprocess
        r = subprocess.run([sys.executable, str(B / "tests/lint_cases.py"), str(B / "demo/cases")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        sh = (B / "demo/run-demo.sh").read_text()
        for scene in ("assay", "warden"):
            self.assertIn(f"{scene}) {scene} ;;", sh)

    def test_live_demo_runs_score_as_the_scene_showed(self):
        """Run the real capture script against a fake gateway that serves the two saved live runs, then the real gate:
        the good agent passes, the rogue one fails on the forbidden tool, exit code 1 (blocks the merge)."""
        import os, subprocess, tempfile, threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        by_agent = {"demo-healthy": "a2a-v1x-demo-healthy-live.json", "demo-rogue": "a2a-v1x-demo-rogue-delete-live.json"}
        seen = []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                agent = self.path.rstrip("/").split("/")[-1]
                seen.append((self.path, body["method"], self.headers.get("A2A-Version")))
                d = rec(by_agent[agent], body["id"])
                data = json.dumps(d).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

            def log_message(self, *_): pass

        srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        d = Path(tempfile.mkdtemp()); env = {**os.environ, "EVAL_NAMESPACE": "guard-demo", "EVAL_REPEAT": "1", "EVAL_PAUSE_S": "0"}
        try:
            for ag in by_agent:
                r = subprocess.run([sys.executable, str(B / "a2a_capture.py"), "--protocol", "1x", "--base-url", f"http://127.0.0.1:{srv.server_port}",
                                    "--cases-dir", str(B / "demo/cases"), "--tier", "full", "--agent", ag, "--repeat", "1", "--out", str(d / f"eval-{ag}")],
                                   capture_output=True, text=True, env=env)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        finally:
            srv.shutdown()
        self.assertEqual({(p.rstrip("/"), m, v) for p, m, v in seen}, {("/agents/kagent/demo-healthy", "SendMessage", "1.0"), ("/agents/kagent/demo-rogue", "SendMessage", "1.0")})
        g = subprocess.run([sys.executable, str(B / "score_and_gate.py"), "--capture-dirs", str(d / "eval-demo-healthy"), str(d / "eval-demo-rogue"),
                            "--repeat", "1", "--expect-agents", "demo-healthy", "demo-rogue", "--out", str(d / "report")], capture_output=True, text=True)
        self.assertEqual(g.returncode, 1, g.stdout + g.stderr)
        self.assertIn("forbidden tool used: k8s_delete_resource", g.stdout)
        self.assertRegex(g.stdout, r"demo-healthy-lists-pods \| demo-healthy \| \*\*pass\*\*")
