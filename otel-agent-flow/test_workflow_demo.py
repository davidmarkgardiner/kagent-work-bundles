import json
import threading
import subprocess
import sys
from pathlib import Path
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from workflow_demo import Handler, model_reply
import yaml


class WorkflowTests(unittest.TestCase):
    def test_post_renderer_omits_empty_documents_and_preserves_authorization(self):
        native = {"frontendPolicies": {"substrateEgressActorResolution": {"host": "api.ate-system.svc:443"},
                                      "accessLog": {"add": {"actor": "native-identity"}}}}
        documents = [None, {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "atenet-egress-agentgateway-config"},
                           "data": {"config.yaml": yaml.safe_dump(native)}},
                     None, {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "atenet-egress"},
                            "spec": {"template": {"metadata": {"labels": {"app": "atenet-egress"}}}}}]
        result = subprocess.run([sys.executable, str(Path(__file__).parent / "scripts/substrate-post-render.py"),
                                 "--endpoint", "http://collector:4317"], input=yaml.safe_dump_all(documents),
                                check=True, text=True, capture_output=True)
        output = list(yaml.safe_load_all(result.stdout))
        self.assertTrue(all(isinstance(d, dict) and d.get("kind") for d in output))
        config = yaml.safe_load(output[0]["data"]["config.yaml"])
        self.assertEqual(config["frontendPolicies"]["substrateEgressActorResolution"], native["frontendPolicies"]["substrateEgressActorResolution"])
        self.assertEqual(config["frontendPolicies"]["accessLog"]["add"], {"actor": "native-identity"})

    def test_fixture_model_calls_declared_tools_then_completes(self):
        payload = {"messages": [{"role": "user", "content": "DEMO_WORKFLOW=inventory"}],
                   "tools": [{"function": {"name": name}} for name in ["get_inventory_status", "get_recent_alerts"]]}
        first, reason = model_reply(payload)
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(first["tool_calls"][0]["function"]["name"], "get_inventory_status")
        payload["messages"].append(first)
        second, _ = model_reply(payload)
        self.assertEqual(second["tool_calls"][0]["function"]["name"], "get_recent_alerts")
        payload["messages"].append(second)
        final, reason = model_reply(payload)
        self.assertEqual(reason, "stop")
        self.assertIn("SIMULATED_WORKFLOW_COMPLETE", final["content"])

    def test_real_mcp_error_call_emits_error_span_with_received_parent(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            parent = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "check_dependency", "arguments": {}}}).encode()
            with patch("workflow_demo.export_event") as exported:
                request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/mcp", body,
                                                 {"Content-Type": "application/json", "traceparent": parent})
                with urllib.request.urlopen(request) as response:
                    result = json.load(response)
                server.shutdown()
                self.assertTrue(result["result"]["isError"])
                self.assertTrue(json.loads(result["result"]["content"][0]["text"])["simulated"])
                call = exported.call_args.args
                self.assertEqual(call[1], "a" * 32)
                self.assertEqual(call[3], "b" * 16)
                self.assertEqual(call[6], 2)
        finally:
            server.shutdown()
            server.server_close()
