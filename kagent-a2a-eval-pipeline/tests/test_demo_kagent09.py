"""The demo on kagent 0.9 (any 0.x): generated v1alpha2 manifests, their fit to the 0.9.12 CRD schemas, the 0.x A2A call,
and Warden on a 0.x Sentinel run. Offline: nothing here has run on a 0.9 cluster (see docs/kagent-versions.md)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo" / "lab"))
import sentinel_manifests  # noqa: E402
import to_v1alpha2  # noqa: E402
import verify_completion  # noqa: E402

SCHEMAS = json.loads((ROOT / "tests/fixtures/kagent-0.9.12-v1alpha2-schemas.json").read_text())["schemas"]
TYPES = {"object": dict, "string": str, "array": list, "boolean": bool, "integer": int, "number": (int, float)}


def problems(obj, schema, path="spec"):
    """Enough of a structural-schema check to catch what the API server would prune or refuse: unknown fields,
    missing required fields, wrong types and values outside an enum."""
    out = []
    t = schema.get("type")
    if t in TYPES and not isinstance(obj, TYPES[t]):
        return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if "enum" in schema and obj not in schema["enum"]:
        out.append(f"{path}: {obj!r} not in {schema['enum']}")
    if isinstance(obj, dict) and "properties" in schema:
        open_ = schema.get("x-kubernetes-preserve-unknown-fields") or schema.get("additionalProperties")
        for k, v in obj.items():
            if k in schema["properties"]:
                out += problems(v, schema["properties"][k], f"{path}.{k}")
            elif not open_:
                out.append(f"{path}.{k}: unknown field (0.9 would drop it)")
        out += [f"{path}.{r}: required" for r in schema.get("required") or [] if r not in obj]
    if isinstance(obj, list) and "items" in schema:
        for i, v in enumerate(obj):
            out += problems(v, schema["items"], f"{path}[{i}]")
    return out


def check_0_9(doc):
    if doc.get("apiVersion", "").startswith("api.kagent.dev"):
        return [f"{doc['kind']} {doc['metadata']['name']}: still a 1.x object"]
    if doc.get("apiVersion") != "kagent.dev/v1alpha2":
        return []
    out = problems(doc["spec"], SCHEMAS[doc["kind"]]["properties"]["spec"])
    if doc["kind"] == "Agent" and not (doc["spec"].get("type") == "Declarative" and "declarative" in doc["spec"]):
        out.append("Agent: type Declarative needs spec.declarative (CRD rule)")
    return out


class GeneratedManifests(unittest.TestCase):
    def test_v1alpha2_copies_are_current(self):
        for name in to_v1alpha2.SOURCES:
            self.assertEqual((ROOT / "demo/lab/v1alpha2" / name).read_text(), to_v1alpha2.render(ROOT / "demo/lab" / name),
                             f"run: python3 demo/lab/to_v1alpha2.py --write ({name} is stale)")

    def test_every_0_9_object_fits_the_0_9_12_schema(self):
        for name in to_v1alpha2.SOURCES:
            for doc in yaml.safe_load_all((ROOT / "demo/lab/v1alpha2" / name).read_text()):
                if doc:
                    self.assertEqual(check_0_9(doc), [], f"{name}: {doc['kind']} {doc['metadata']['name']}")

    def test_same_agents_prompts_and_tools_as_the_1x_files(self):
        for name in to_v1alpha2.SOURCES:
            new = {d["metadata"]["name"]: d for d in yaml.safe_load_all((ROOT / "demo/lab" / name).read_text()) if d and d["kind"] == "Agent"}
            old = {d["metadata"]["name"]: d for d in yaml.safe_load_all((ROOT / "demo/lab/v1alpha2" / name).read_text()) if d and d["kind"] == "Agent"}
            self.assertEqual(set(new), set(old))
            for n in new:
                i, dcl = new[n]["spec"]["template"]["inline"], old[n]["spec"]["declarative"]
                self.assertEqual(i["systemPrompt"], dcl["systemMessage"], n)
                self.assertEqual(i["modelConfig"]["name"], dcl["modelConfig"], n)
                self.assertEqual([t["mcp"]["tools"] for t in i.get("tools") or []], [t["mcpServer"]["toolNames"] for t in dcl.get("tools") or []], n)

    def test_the_bundles_other_v1alpha2_agents_fit_0_9_too(self):
        for f in ["lookout/manifests/mr-security-review-agent.yaml", "completion-gate/manifests/completion-evaluator-agent.yaml",
                  "completion-gate/manifests/sentinel-investigator-agent.yaml"]:
            for doc in yaml.safe_load_all((ROOT / f).read_text()):
                if doc and doc.get("kind") in SCHEMAS:
                    self.assertEqual(check_0_9(doc), [], f"{f}: {doc['metadata']['name']}")

    def test_the_checker_catches_a_1x_only_field(self):
        bad = {"apiVersion": "kagent.dev/v1alpha2", "kind": "ModelConfig", "metadata": {"name": "x"},
               "spec": {"model": "m", "provider": "OpenAI", "openAI": {"apiFormat": "chatCompletions"}}}
        self.assertTrue(any("apiFormat" in p for p in check_0_9(bad)))

    def test_a_sub_agent_without_an_evaluator_name_is_refused(self):
        doc = {"apiVersion": "api.kagent.dev/v1alpha3", "kind": "Agent", "metadata": {"name": "w"},
               "spec": {"template": {"inline": {"modelConfig": {"name": "m"}, "systemPrompt": "p", "tools": [{"subAgent": {"name": "e"}}]}}}}
        with self.assertRaises(ValueError):
            to_v1alpha2.convert(doc)


class Sentinel09(unittest.TestCase):
    ENV = {"KAGENT_API": "0.9", "SENTINEL_MODELCONFIG": "m", "READONLY_MCP_SERVER": "ro-tools", "PYTHON_IMAGE": "python:3.12", "NS": "kagent"}

    def setUp(self):
        self.evaluator, self.worker, self.app = sentinel_manifests.manifests(self.ENV)
        self.contract = yaml.safe_load((ROOT / "completion-gate/contracts/sentinel-investigator.yaml").read_text())

    def test_no_harness_needed_and_all_objects_fit_0_9(self):
        for d in (self.evaluator, self.worker):
            self.assertEqual(check_0_9(d), [], d["metadata"]["name"])

    def test_evaluator_is_the_contracts_agent_and_the_worker_calls_it_as_a_tool(self):
        self.assertEqual(self.evaluator["metadata"]["name"], self.contract["evaluator"]["agent"])
        self.assertNotIn("guard-demo-sentinel", self.evaluator["metadata"].get("labels") or {})   # never removed by the demo cleanup
        agent_tools = [t["agent"]["name"] for t in self.worker["spec"]["declarative"]["tools"] if t["type"] == "Agent"]
        self.assertEqual(agent_tools, [self.contract["evaluator"]["agent"]])

    def test_worker_is_the_bundles_v1alpha2_sentinel_agent_renamed(self):
        src = yaml.safe_load((ROOT / "completion-gate/manifests/sentinel-investigator-agent.yaml").read_text())
        self.assertEqual(self.worker["spec"]["declarative"]["systemMessage"], src["spec"]["declarative"]["systemMessage"])
        self.assertEqual(self.worker["metadata"]["name"], "demo-sentinel")

    def test_warden_passes_a_real_0x_sentinel_run_against_this_worker(self):
        receipt = json.loads((ROOT / "tests/fixtures/a2a-live-agent-tool-completed.json").read_text())
        out = verify_completion.verify(self.contract, receipt, agent_crd=self.worker)
        self.assertEqual((out["verdict"], out["route"]), ("PASS", "ticket"), out["failures"])

    def test_parts_split_evaluator_from_workload(self):
        self.assertEqual([d["kind"] for d in sentinel_manifests.manifests(self.ENV, "evaluator")], ["Agent"])
        self.assertEqual([d["kind"] for d in sentinel_manifests.manifests(self.ENV, "workload")], ["Agent", "Deployment"])


class Ask0x(unittest.TestCase):
    """ask_agent.py --protocol 0.7 over real HTTP against a server that answers with a recorded 0.x run."""

    def test_message_send_to_the_0x_path_and_a_completed_summary(self):
        fixture = json.loads((ROOT / "tests/fixtures/a2a-live-agent-tool-completed.json").read_text())
        seen = {}

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                seen.update(path=self.path, method=body["method"], role=body["params"]["message"]["role"])
                reply = json.dumps({**fixture, "id": body["id"]}).encode()
                self.send_response(200); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(reply)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as d:
                r = subprocess.run([sys.executable, str(ROOT / "demo/ask_agent.py"), "--protocol", "0.7",
                                    "--base", f"http://127.0.0.1:{srv.server_address[1]}/api/a2a/kagent", "--agent", "demo-sentinel",
                                    "--text", "hi", "--out", f"{d}/r.json"], capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                s = json.loads(r.stdout)
                self.assertTrue(Path(f"{d}/r.json").exists())
        finally:
            srv.shutdown(); srv.server_close()
        self.assertEqual(seen, {"path": "/api/a2a/kagent/demo-sentinel/", "method": "message/send", "role": "user"})
        self.assertEqual(s["state"], "COMPLETED")
        self.assertIn("kagent__NS__completion_evaluator_agent", s["tools"])

    def test_unreachable_agent_is_a_failure_not_a_hang(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(ROOT / "demo/ask_agent.py"), "--protocol", "0.7", "--base", "http://127.0.0.1:9/api/a2a/kagent",
                                "--agent", "x", "--text", "hi", "--out", f"{d}/r.json"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["state"], "ERROR")


class Runner(unittest.TestCase):
    def test_every_agent_lookup_follows_kagent_api(self):
        text = (ROOT / "demo/run-demo.sh").read_text()
        self.assertIn('KAGENT_API="${KAGENT_API:-1x}"', text)
        body = text.split("k() {", 1)[1]                      # after the one place the switch is made
        self.assertNotIn("agents.api.kagent.dev", body)
        self.assertNotIn("template.inline.modelConfig", body)
        self.assertNotIn(' get agent "', body)
        self.assertIn('--protocol "$PROTO"', body)

    def test_example_env_documents_the_switch(self):
        self.assertIn("KAGENT_API=", (ROOT / "demo/demo.env.example").read_text())


if __name__ == "__main__":
    unittest.main()
