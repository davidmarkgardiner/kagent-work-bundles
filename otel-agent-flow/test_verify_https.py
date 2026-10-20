"""Exercise connected verification without network access or model calls."""
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import urllib.error


class ConnectedVerificationTests(unittest.TestCase):
    def test_client_attempt_cannot_satisfy_server_completion(self):
        pairs = runpy.run_path(str(Path(__file__).parent / "scripts/verify-https.py"))["server_tool_pairs"]
        attempt = {"service": "kubernetes-mcp", "kind": "client", "status": "ok", "attributes": {"mcp.tool.name": "read_status"}}
        self.assertEqual(pairs([attempt]), set())
        self.assertEqual(pairs([{**attempt, "kind": "server", "toolExecution": "server"}]), {("kubernetes-mcp", "read_status")})

    def run_verifier(self, mode, custom, simulated=False, multiple=False):
        submitted = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("Read the workload status using read_status. Do not change anything.")
            argv = ["verify-https.py", "--url", "https://flow.example.invalid", "--output", str(output)]
            if custom:
                argv += ["--prompt-file", str(prompt), "--expect-tool", "read_status", "--tool-service", "kubernetes-mcp"]
            if multiple:
                argv = argv[:-4] + ["--expect-mcp", "kubernetes-mcp:read_status", "--expect-mcp", "gitlab-mcp:read_project"]
            invocation = {"traceId": "request", "sessionId": "session", "status": "completed", "text": "Read complete",
                          "startedAt": 1, "finishedAt": 2}
            spans = [{"service": "atelet", "name": name, "attributes": {}, "status": "ok"} for name in
                     ["ateom.Ateom/RestoreWorkload", "ateom.Ateom/CheckpointWorkload"]]
            spans.append({"service": "kubernetes-mcp", "name": "read_status", "status": "ok", "kind": "server", "toolExecution": "server",
                          "attributes": {"mcp.tool.name": "read_status", "flow.simulated": simulated}})
            if multiple:
                spans.append({"service": "gitlab-mcp", "name": "read_project", "status": "ok", "kind": "server", "toolExecution": "server", "attributes": {"gen_ai.tool.name": "read_project"}})
            trace = {"traceId": "request", "spans": spans, "spanCount": len(spans), "inputTokens": 10,
                     "outputTokens": 5, "modelCalls": [], "costUsd": None}
            state = {"runtime": {"demoMode": mode}, "invocation": invocation, "traces": [trace],
                     "sessionActivity": {"actorName": "actor", "traceIds": ["request"], "components":
                         ["client", "kagent", "substrate", "worker", "actor", "agentgateway", "model", "mcp"],
                         "states": [{"state": "running"}, {"state": "suspended"}]}}

            def open_request(request, **_kwargs):
                path = request.full_url.removeprefix("https://flow.example.invalid")
                payload = json.loads(request.data) if request.data else None
                status, body = 200, {}
                if path in {"/v1/traces", "/v1/logs"}:
                    status = 404
                elif path == "/api/invoke":
                    if request.headers.get("Origin") == "https://untrusted.invalid":
                        status = 403
                    elif not payload["prompt"]:
                        status = 400
                    else:
                        submitted.append(payload["prompt"])
                        status, body = 202, {"traceId": "request"}
                elif path == "/api/state":
                    body = state
                elif path == "/api/logs":
                    body = {"logs": [{"event": "ate.actor.state_changed", "attributes": {"ate.actor.name": "actor"}}]}
                if status >= 400:
                    raise urllib.error.HTTPError(request.full_url, status, "expected", {}, io.BytesIO(b"{}"))
                response = io.BytesIO(json.dumps(body).encode())
                response.status = status
                return response

            with patch("sys.argv", argv), patch("urllib.request.build_opener") as build, patch("builtins.print"), patch("sys.stderr", new_callable=io.StringIO):
                build.return_value.open.side_effect = open_request
                try:
                    runpy.run_path(str(Path(__file__).parent / "scripts/verify-https.py"), run_name="__main__")
                except (SystemExit, AssertionError) as error:
                    return submitted, error, None
            return submitted, None, json.loads(output.read_text())

    def test_connected_mode_requires_reviewed_custom_prompt(self):
        submitted, error, receipt = self.run_verifier("connected", custom=False)
        self.assertEqual(submitted, [])
        self.assertIsInstance(error, SystemExit)
        self.assertIsNone(receipt)

    def test_connected_receipt_requires_expected_real_server_tool(self):
        submitted, error, receipt = self.run_verifier("connected", custom=True)
        self.assertIsNone(error)
        self.assertEqual(len(submitted), 1)
        self.assertNotIn("DEMO_WORKFLOW", submitted[0])
        self.assertEqual(receipt["workflows"][0]["tools"], ["read_status"])
        self.assertEqual(receipt["workflows"][0]["toolService"], "kubernetes-mcp")

    def test_live_tools_receipt_requires_named_tools_from_both_servers(self):
        submitted, error, receipt = self.run_verifier("live-tools", custom=True, multiple=True)
        self.assertIsNone(error)
        self.assertEqual(len(submitted), 1)
        self.assertEqual(receipt["workflows"][0]["expectedServerTools"], [["kubernetes-mcp", "read_status"], ["gitlab-mcp", "read_project"]])

    def test_simulated_tool_cannot_pass_connected_proof(self):
        _, error, receipt = self.run_verifier("connected", custom=True, simulated=True)
        self.assertIsInstance(error, AssertionError)
        self.assertIsNone(receipt)


if __name__ == "__main__":
    unittest.main()
