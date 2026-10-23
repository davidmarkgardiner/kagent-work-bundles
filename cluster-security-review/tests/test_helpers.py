#!/usr/bin/env python3
"""Offline regression fixtures; fake kubectl/curl never contact a cluster."""
import copy
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

import yaml

BUNDLE = Path(__file__).resolve().parents[1]
FAKE_TOOL = r'''#!/usr/bin/env python3
import json, os
from pathlib import Path
import sys, time
root=Path(os.environ['FIXTURES'])
args=sys.argv[1:]
with (root/'calls').open('a') as f: f.write(Path(sys.argv[0]).name+' '+json.dumps(args)+'\n')
if Path(sys.argv[0]).name == 'kubectl':
    if 'kustomize' in args:
        print((Path(args[args.index('kustomize')+1])/'agent.yaml').read_text(), end=''); sys.exit()
    if 'get' in args:
        index_file=root/'get-index'
        i=int(index_file.read_text()) if index_file.exists() else 0
        docs=json.loads((root/'agents').read_text())
        print(json.dumps(docs[min(i,len(docs)-1)])); index_file.write_text(str(i+1)); sys.exit()
    if 'port-forward' in args:
        if os.environ.get('PF_FAIL'):
            print('fixture: forbidden controller port-forward',file=sys.stderr); sys.exit(1)
        time.sleep(30); sys.exit()
    sys.exit('unexpected kubectl command')
if '-X' in args:
    (root/'payload').write_text(args[args.index('-d')+1])
    if '-o' in args: Path(args[args.index('-o')+1]).write_bytes((root/'response').read_bytes())
    print(os.environ.get('HTTP_CODE','200'),end='')
    sys.exit(int(os.environ.get('CURL_RC','0')))
time.sleep(0.03)
if os.environ.get('PF_FAIL'): sys.exit(7)
print((root/'listed').read_text(),end='')
sys.exit(int(os.environ.get('CURL_GET_RC','0')))
'''


def ready(generation=2, observed=2, per_condition=False):
    doc = {"metadata": {"generation": generation}, "status": {"conditions": [
        {"type": name, "status": "True"} for name in ("Accepted", "Ready")]}}
    if per_condition:
        for condition in doc["status"]["conditions"]:
            condition["observedGeneration"] = observed
    elif observed is not None:
        doc["status"]["observedGeneration"] = observed
    return doc


class Helpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / "bundle"
        for name in ("scripts", "manifests", "references"):
            shutil.copytree(BUNDLE / name, self.bundle / name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("kubectl", "curl"):
            tool = self.bin / name
            tool.write_text(FAKE_TOOL)
            tool.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        FIXTURES=str(self.root), PYTHONOPTIMIZE="1")
        self.write("response", {"jsonrpc": "2.0", "result": {"kind": "task", "status": {"state": "completed"},
                   "artifacts": [{"parts": [{"kind": "text", "text": "review"}]}]}})
        self.write("agents", [ready()])
        self.write("listed", {"agents": [{"name": "cluster-security-review"}]})

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def run_helper(self, name, *args):
        cmd = (["python3"] if name.endswith(".py") else ["bash"]) + [str(self.bundle / "scripts" / name), *args]
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=8)

    def manifest(self):
        return yaml.safe_load((self.bundle / "manifests/agent.yaml").read_text())

    def save_manifest(self, doc):
        (self.bundle / "manifests/agent.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))

    def invoke(self, *args):
        return self.run_helper("kagent-a2a-invoke.sh", "--agent", "cluster-security-review", "--text", "fixture",
                               "--url", "http://fixture.invalid", *args)

    def verify(self, *args):
        return self.run_helper("kagent-verify-agent.sh", "--agent", "cluster-security-review", "--timeout", "0", *args)

    def calls(self):
        path = self.root / "calls"
        return path.read_text() if path.exists() else ""

    def test_environment_adaptations_pass_without_checksums(self):
        doc = self.manifest()
        doc["metadata"]["namespace"] = "security-review"
        doc["spec"]["declarative"]["modelConfig"] = "bank-model"
        doc["spec"]["declarative"]["tools"][0]["mcpServer"]["name"] = "local-server"
        self.save_manifest(doc)
        result = self.run_helper("validate-manifests.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_closed_allowlist_rejects_execution_routes_even_optimized(self):
        baseline = self.manifest()
        for name in ("k8s_label_resource", "k8s_annotate_resource", "k8s_remove_label",
                     "k8s_create_resource_from_url", "k8s_scale_resource", "k8s_rollout_restart",
                     "k8s_check_service_connectivity", "unknown_tool"):
            with self.subTest(tool=name):
                doc = copy.deepcopy(baseline)
                doc["spec"]["declarative"]["tools"][0]["mcpServer"]["toolNames"].append(name)
                self.save_manifest(doc)
                result = self.run_helper("validate-manifests.sh")
                self.assertNotEqual(result.returncode, 0, result.stdout)
        changes = [lambda d: d["spec"].update(skills=[]),
                   lambda d: d["spec"]["declarative"].update(env={"SHELL": "sh"}),
                   lambda d: d["spec"]["declarative"].update(runtime="shell"),
                   lambda d: d["spec"]["declarative"]["tools"].append({"type": "Agent", "agent": {"name": "writer"}})]
        for change in changes:
            doc = copy.deepcopy(baseline)
            change(doc)
            self.save_manifest(doc)
            self.assertNotEqual(self.run_helper("validate-manifests.sh").returncode, 0)

    def test_missing_catalog_fails_closed(self):
        result = self.run_helper("validate-agent-cr.py", str(self.bundle / "manifests/agent.yaml"), "--catalog", str(self.root / "missing"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("catalog not found", result.stderr)

    def test_mutation_catalog_aliases_rejected_by_general_lint(self):
        baseline = self.manifest()
        for tool in ("k8s_label_resource", "k8s_annotate_resource", "k8s_remove_label", "k8s_remove_annotation",
                     "k8s_create_resource_from_url", "k8s_scale_resource", "k8s_rollout_restart"):
            doc = copy.deepcopy(baseline)
            doc["spec"]["declarative"]["tools"][0]["mcpServer"]["toolNames"].append(tool)
            self.save_manifest(doc)
            with (self.bundle / "references/tool-catalog.md").open("a") as f:
                f.write(f"\n| `{tool}` | fixture |\n")
            result = self.run_helper("validate-agent-cr.py", str(self.bundle / "manifests/agent.yaml"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL triage-no-write-tools", result.stdout)

    def test_incomplete_task_text_never_succeeds_in_any_output_mode(self):
        for state in ("failed", "canceled", "input-required", "auth-required", "working", "submitted", "UNKNOWN", None):
            for mode in ([], ["--raw"], ["--json"]):
                with self.subTest(state=state, mode=mode):
                    response = {"jsonrpc": "2.0", "result": {"kind": "task", "status": {}, "artifacts": [
                        {"parts": [{"kind": "text", "text": "plausible partial report"}]}]}}
                    if state is not None:
                        response["result"]["status"]["state"] = state
                    self.write("response", response)
                    receipt = self.root / "receipt"
                    result = self.invoke("--receipt-file", str(receipt), *mode)
                    self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
                    self.assertEqual(receipt.read_bytes(), (self.root / "response").read_bytes())
                    self.assertEqual(stat.S_IMODE(receipt.stat().st_mode), 0o600)
                    if mode == ["--raw"]:
                        self.assertEqual(result.stdout.strip(), (self.root / "response").read_text())

    def test_completed_artifact_history_and_message(self):
        result = self.invoke()
        self.assertEqual((result.returncode, result.stdout), (0, "review\n"), result.stderr)
        self.write("response", {"result": {"kind": "task", "status": {"state": "completed"}, "history": [
            {"role": "user", "parts": [{"kind": "text", "text": "input"}]},
            {"role": "agent", "parts": [{"kind": "text", "text": "final history"}]}]}})
        result = self.invoke("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["text"], "final history")
        self.write("response", {"result": {"kind": "message", "role": "agent", "messageId": "m1",
                                          "parts": [{"kind": "text", "text": "message reply"}]}})
        result = self.invoke()
        self.assertEqual((result.returncode, result.stdout), (0, "message reply\n"), result.stderr)

    def test_statusless_artifacts_and_user_messages_fail(self):
        for response in ({"result": {"artifacts": [{"parts": [{"kind": "text", "text": "unsafe"}]}]}},
                         {"result": {"kind": "message", "role": "user", "messageId": "m", "parts": []}}):
            self.write("response", response)
            self.assertEqual(self.invoke("--raw").returncode, 6)

    def test_timeout_has_correlation_and_preserves_partial_receipt(self):
        self.env["CURL_RC"] = "28"
        result = self.invoke("--context-id", "explicit-context", "--receipt-file", str(self.root / "receipt"))
        self.assertEqual(result.returncode, 4)
        self.assertIn("context_id=explicit-context", result.stderr)
        self.assertIn("request_id=invoke-", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads((self.root / "payload").read_text())["params"]["message"]["contextId"], "explicit-context")
        self.assertTrue((self.root / "receipt").exists())
        self.assertEqual(self.calls().count('"POST"'), 1)

    def test_payload_context_honors_explicit_override(self):
        self.write("params", {"message": {"contextId": "payload-context", "parts": [{"kind": "text", "text": "fixture"}]}})
        result = self.invoke("--payload-file", str(self.root / "params"), "--context-id", "explicit-context")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads((self.root / "payload").read_text())
        self.assertEqual(payload["params"]["message"]["contextId"], "explicit-context")

    def test_http_and_rpc_errors_keep_raw_receipts(self):
        for http, body in (("403", {"error": {"message": "denied"}}), ("200", {"error": {"message": "runtime unavailable"}})):
            self.env["HTTP_CODE"] = http
            self.write("response", body)
            receipt = self.root / "receipt"
            result = self.invoke("--raw", "--receipt-file", str(receipt))
            self.assertEqual(result.returncode, 3)
            self.assertEqual(result.stdout.strip(), receipt.read_text())

    def test_stale_generation_never_reaches_api(self):
        for per_condition in (False, True):
            with self.subTest(per_condition=per_condition):
                self.write("agents", [ready(observed=1, per_condition=per_condition)])
                result = self.verify()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("port-forward", self.calls())
                self.assertIn("current-generation readiness not established", result.stderr)

    def test_missing_generation_is_explicit_blocker(self):
        self.write("agents", [ready(observed=None)])
        result = self.verify()
        self.assertEqual(result.returncode, 2)
        self.assertIn("generation evidence unavailable", result.stderr)
        self.assertNotIn("port-forward", self.calls())

    def test_current_generations_pass_and_new_generation_rejected(self):
        for per_condition in (False, True):
            self.write("agents", [ready(per_condition=per_condition)])
            result = self.verify("--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["api_listed"])
        (self.root / "get-index").unlink()
        self.write("agents", [ready(), ready(generation=3, observed=3)])
        result = self.verify()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn("generation/readiness changed", result.stderr)

    def test_updated_conditions_can_converge(self):
        self.write("agents", [ready(observed=1), ready(), ready()])
        result = self.run_helper("kagent-verify-agent.sh", "--agent", "cluster-security-review", "--timeout", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pending_first_reconcile_can_become_ready(self):
        self.write("agents", [{"metadata": {"generation": 2}}, ready(), ready()])
        result = self.run_helper("kagent-verify-agent.sh", "--agent", "cluster-security-review", "--timeout", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("api-listed generation=2", result.stdout)

    def test_port_forward_failure_distinct_from_absent_agent(self):
        self.env["PF_FAIL"] = "1"
        result = self.verify()
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("forbidden controller port-forward", result.stderr)
        self.assertNotIn("agent absent", result.stdout)

    def test_successful_transport_can_report_absent_agent(self):
        self.write("listed", {"agents": []})
        result = self.verify()
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("transport succeeded", result.stdout)


if __name__ == "__main__":
    unittest.main()
