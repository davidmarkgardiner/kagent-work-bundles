import io
import os
import sys
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import backend
from standalone_call import invoke_standalone

TARGETS = [
    {"id": "substrate", "mode": "substrate", "label": "With Substrate"},
    {"id": "standalone", "mode": "standalone", "label": "Without Substrate", "url": "http://standalone.invalid:8080/"},
]


class ReadOnlyViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), backend.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_read_only_viewer_rejects_invoke_before_starting_any_execution(self):
        request = urllib.request.Request(self.url + "/api/invoke", b'{"prompt":"must not execute"}', {"Content-Type": "application/json"})
        with patch.dict(backend.os.environ, {"READ_ONLY_VIEWER": "true"}), patch("backend.invoke") as invoke:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request, timeout=5)
            self.assertEqual(error.exception.code, 403)
            self.assertIn("read-only", json.load(error.exception)["error"].lower())
            invoke.assert_not_called()
            self.assertFalse(backend.INVOKING.locked())

    def test_passive_viewer_advertises_no_execution_targets(self):
        with patch.dict(backend.os.environ, {"READ_ONLY_VIEWER": "true", "EXECUTION_TARGETS": "invalid configuration unused by viewer"}):
            with urllib.request.urlopen(self.url + "/api/state", timeout=5) as response:
                state = json.load(response)
        self.assertTrue(state["runtime"]["readOnlyViewer"])
        self.assertEqual(state["runtime"]["executionTargets"], [])
        self.assertIn("nativeActivities", state)

    def test_actor_activity_response_is_bounded_for_many_native_requests(self):
        store = backend.ActivityStore()
        attributes = [{"key": k, "value": {"stringValue": v}} for k, v in {
            "service.name": "native-agent", "kagent.runtime": "adk-go",
            "gen_ai.main_agent.id": "demo/native-agent", "gen_ai.main_agent.name": "native-agent"}.items()]
        spans = [{"traceId": f"{n:032x}", "spanId": f"{n:016x}", "name": "generate_content test",
            "startTimeUnixNano": "1000000000", "endTimeUnixNano": "1200000000",
            "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in {
                "gen_ai.operation.name": "generate_content", "gen_ai.request.model": "test",
                "ate.actor.name": "shared-actor"}.items()]} for n in range(1, 201)]
        store.ingest({"resourceSpans": [{"resource": {"attributes": attributes}, "scopeSpans": [{"spans": spans}]}]})
        with patch("backend.STORE", store):
            with urllib.request.urlopen(self.url + "/api/state", timeout=5) as response:
                payload = response.read()
        state = json.loads(payload)
        self.assertEqual(len(state["traces"]), 200)
        self.assertLessEqual(len(state["nativeActivities"]), 8)
        self.assertLess(len(payload), 1024 * 1024)


class ExecutionTests(unittest.TestCase):
    def test_runtime_id_cannot_supply_an_arbitrary_route(self):
        with patch.dict(backend.os.environ, {"EXECUTION_TARGETS": json.dumps(TARGETS)}):
            self.assertEqual(backend.execution_target("standalone")["url"], TARGETS[1]["url"])
            self.assertIsNone(backend.execution_target("http://untrusted.invalid/"))
            self.assertIsNone(backend.execution_target({"url": "http://untrusted.invalid/"}))
            self.assertEqual(backend.invocation_prompt({"prompt": "check", "runtime": "standalone"}), "check")

    def test_duplicate_runtime_ids_and_credential_urls_are_rejected(self):
        for targets in ([TARGETS[0], TARGETS[0]], [{**TARGETS[1], "url": "http://user:password@standalone.invalid/"}]):
            with patch.dict(backend.os.environ, {"EXECUTION_TARGETS": json.dumps(targets)}), self.assertRaises(ValueError):
                backend.execution_targets()

    def test_standalone_invoke_never_creates_a_substrate_session(self):
        with patch("standalone_call.invoke_standalone", return_value="Real read complete") as native, patch("substrate_call.invoke_session") as substrate, patch("backend.post", return_value={}) as export, patch.dict(backend.INVOCATION, {}, clear=True):
            self.assertTrue(backend.INVOKING.acquire(blocking=False))
            backend.invoke("Inspect workloads", "1" * 32, TARGETS[1])
            substrate.assert_not_called()
            self.assertEqual(native.call_args.args[3], TARGETS[1]["url"])
            self.assertNotIn("actorName", backend.INVOCATION)
            self.assertEqual(backend.INVOCATION["executionMode"], "standalone")
            self.assertEqual(backend.INVOCATION["status"], "completed")
            self.assertEqual(export.call_count, 1)
            self.assertNotIn("Inspect workloads", json.dumps(export.call_args.args[1]))
            self.assertIn("standalone", json.dumps(export.call_args.args[1]))

    def test_direct_native_a2a_uses_terminal_result_and_trace_context(self):
        response = io.BytesIO(json.dumps({"result": {"task": {"status": {"state": "TASK_STATE_COMPLETED"}, "artifacts": [{"parts": [{"text": "Workloads read"}]}]}}}).encode())
        invocation = {}
        with patch("urllib.request.urlopen", return_value=response) as call:
            text = invoke_standalone("check", {"traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01"}, invocation, TARGETS[1]["url"])
        self.assertEqual(text, "Workloads read")
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body["method"], "SendMessage")
        self.assertEqual(body["params"]["message"]["role"], "ROLE_USER")
        self.assertFalse(body["params"]["configuration"]["returnImmediately"])
        self.assertIn("Traceparent", request.headers)
        self.assertNotIn("actorName", invocation)

    def test_input_required_is_not_automatically_approved(self):
        response = io.BytesIO(json.dumps({"result": {"task": {"status": {"state": "TASK_STATE_INPUT_REQUIRED"}}}}).encode())
        with patch("urllib.request.urlopen", return_value=response), self.assertRaises(ValueError):
            invoke_standalone("check", {}, {}, TARGETS[1]["url"])

    def test_oversized_standalone_response_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"x" * (1024 * 1024 + 1))), self.assertRaises(ValueError):
            invoke_standalone("check", {}, {}, TARGETS[1]["url"])

    def test_standalone_installer_skips_platform_and_rollback_requirements(self):
        root = Path(__file__).parent
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            values = temporary / "values.yaml"
            values.write_text("execution: {mode: standalone}\ningress: {mode: local}\n")
            launcher = temporary / "python3"
            launcher.write_text("#!" + sys.executable + "\nimport os,sys\nif sys.argv[1].endswith('preflight.py'): sys.exit(0)\nif sys.argv[1].endswith('platform-telemetry.py'): sys.exit(99)\nos.execv(" + repr(sys.executable) + ", [" + repr(sys.executable) + "]+sys.argv[1:])\n")
            launcher.chmod(0o755)
            for tool, code in [("helm", 0), ("kubectl", 99)]:
                binary = temporary / tool
                binary.write_text("#!/bin/sh\nexit " + str(code) + "\n")
                binary.chmod(0o755)
            environment = {**os.environ, "PATH": str(temporary) + os.pathsep + os.environ["PATH"], "KUBE_CONTEXT": "standalone-test"}
            environment.pop("FLOW_STATE_DIR", None)
            result = subprocess.run(["bash", str(root / "scripts/deploy.sh"), str(values)], text=True, capture_output=True, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Standalone-only mode", result.stdout)

    def test_standalone_preflight_does_not_query_platform_apis(self):
        root = Path(__file__).parent
        rendered = subprocess.run(["helm", "template", "flow-demo", str(root / "deploy/chart"), "--set", "execution.mode=standalone"], text=True, capture_output=True, check=True).stdout
        calls = []
        def run(command, **_kwargs):
            calls.append(command)
            if command[:2] == ["helm", "template"]:
                return subprocess.CompletedProcess(command, 0, stdout=rendered)
            if command[0] == "kubectl" and "secret" in command:
                return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"type": "kubernetes.io/tls", "data": {"tls.crt": "test", "tls.key": "test"}}))
            raise AssertionError("Unexpected platform dependency in standalone mode: " + repr(command))
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory) / "values.yaml"
            values.write_text("execution: {mode: standalone}\ningress: {mode: local}\n")
            with patch("subprocess.run", side_effect=run), patch("sys.argv", ["preflight.py", "--context", "standalone-test", "--values", str(values)]), patch("builtins.print"):
                runpy.run_path(str(root / "scripts/preflight.py"), run_name="__main__")
        self.assertEqual(len(calls), 2)
