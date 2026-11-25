"""The demo's Sentinel scene: the detection code, the generated manifests, and that the demo agent still meets the real contract."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
sys.path.insert(0, str(ROOT / "demo" / "lab"))
sys.path.insert(0, str(ROOT))
import sentinel_check  # noqa: E402
import sentinel_manifests  # noqa: E402
import verify_completion  # noqa: E402

ENV = {"HARNESS": "h", "SENTINEL_MODELCONFIG": "glm", "READONLY_MCP_SERVER": "ro-tools", "PYTHON_IMAGE": "python:3.12", "NS": "kagent",
       "APP_NS": "guard-demo"}


def pod(name="whisky-app-86484589f5-abcde", rs="whisky-app-86484589f5", h="86484589f5", waiting=None, restarts=0, ns="guard-demo"):
    meta = {"name": name, "namespace": ns, "labels": {"pod-template-hash": h} if h else {}}
    if rs:
        meta["ownerReferences"] = [{"kind": "ReplicaSet", "name": rs}]
    state = {"waiting": {"reason": waiting}} if waiting else {"running": {}}
    return {"metadata": meta, "status": {"containerStatuses": [{"name": "app", "state": state, "restartCount": restarts}]}}


class Detection(unittest.TestCase):
    def test_crashloop_becomes_one_finding_on_the_deployment(self):
        fs = sentinel_check.findings({"items": [pod(waiting="CrashLoopBackOff", restarts=4)]}, "lab")
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["incident_key"], "demo/lab/guard-demo/Deployment/whisky-app/crashloop")
        self.assertEqual((fs[0]["reason"], fs[0]["restarts"]), ("CrashLoopBackOff", 4))

    def test_restarts_alone_count_and_healthy_pods_do_not(self):
        self.assertEqual(sentinel_check.findings({"items": [pod(restarts=1)]}, "lab"), [])
        fs = sentinel_check.findings({"items": [pod(restarts=3)]}, "lab")
        self.assertEqual(fs[0]["finding_type"], "restarting")
        self.assertEqual(sentinel_check.findings({"items": [pod(restarts=2)]}, "lab", restarts=2)[0]["finding_type"], "restarting")

    def test_two_pods_of_one_deployment_are_one_finding_and_a_bare_pod_is_named_itself(self):
        two = [pod(waiting="CrashLoopBackOff"), pod(name="whisky-app-86484589f5-zzzzz", waiting="CrashLoopBackOff")]
        self.assertEqual(len(sentinel_check.findings({"items": two}, "lab")), 1)
        bare = sentinel_check.findings({"items": [pod(name="lonely", rs=None, h=None, waiting="ImagePullBackOff")]}, "lab")
        self.assertEqual(bare[0]["incident_key"], "demo/lab/guard-demo/Pod/lonely/image-pull")

    def test_message_carries_the_key_and_marks_the_finding_as_data(self):
        f = sentinel_check.findings({"items": [pod(waiting="CrashLoopBackOff")]}, "lab")[0]
        m = sentinel_check.message(f)
        self.assertIn(f["incident_key"], m)
        self.assertIn("untrusted data", m)

    def test_cli_exit_codes(self):
        cli = [sys.executable, str(ROOT / "demo" / "sentinel_check.py"), "--cluster", "lab"]
        ok = subprocess.run(cli, input=json.dumps({"items": [pod()]}), capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        hit = subprocess.run(cli, input=json.dumps({"items": [pod(waiting="CrashLoopBackOff")]}), capture_output=True, text=True)
        self.assertEqual(hit.returncode, 1)
        self.assertIn("whisky-app", hit.stdout)
        self.assertEqual(subprocess.run(cli, input="not json", capture_output=True, text=True).returncode, 3)


class Manifests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = sentinel_manifests.manifests(ENV)
        cls.template, cls.agent, cls.app = cls.docs

    def test_everything_is_labelled_for_cleanup(self):
        for d in self.docs:
            self.assertEqual(d["metadata"]["labels"]["guard-demo-sentinel"], "true", d["kind"])

    def test_the_demo_agent_is_the_real_sentinel_agent_renamed(self):
        src = yaml.safe_load((ROOT / "completion-gate/manifests/sentinel-investigator-agent-v1alpha3.yaml").read_text())
        a, s = self.agent["spec"]["template"]["inline"], src["spec"]["template"]["inline"]
        self.assertEqual(a["systemPrompt"], s["systemPrompt"])
        self.assertEqual([t["mcp"]["tools"] for t in a["tools"] if "mcp" in t], [t["mcp"]["tools"] for t in s["tools"] if "mcp" in t])
        self.assertEqual(a["modelConfig"], {"name": "glm"})
        sub = next(t["subAgent"] for t in a["tools"] if "subAgent" in t)
        contract = yaml.safe_load((ROOT / "completion-gate/contracts/sentinel-investigator.yaml").read_text())
        self.assertEqual(sub["name"], contract["evaluator"]["subAgent"])      # verify_completion looks for this name
        self.assertEqual(sub["templateRef"]["name"], self.template["metadata"]["name"])

    def test_the_demo_agent_passes_warden_crd_check(self):
        contract = yaml.safe_load((ROOT / "completion-gate/contracts/sentinel-investigator.yaml").read_text())
        receipt = json.loads((ROOT / "tests/fixtures/a2a-v1x-sentinel-pass-live.json").read_text())
        out = verify_completion.verify(contract, receipt, agent_crd=self.agent)
        self.assertEqual((out["verdict"], out["route"]), ("PASS", "ticket"), out["failures"])

    def test_evaluator_is_generated_from_the_contract(self):
        self.assertEqual(self.template["kind"], "AgentTemplate")
        self.assertIn("sentinel-investigation", self.template["spec"]["systemPrompt"])
        self.assertEqual(self.template["spec"]["tools"], [])                # the evaluator has no tools

    def test_the_app_fails_for_a_config_reason_the_agent_must_find_in_the_logs(self):
        c = self.app["spec"]["template"]["spec"]["containers"][0]
        self.assertNotIn("env", c)                                           # WHISKY_DB_URL is deliberately missing
        r = subprocess.run([sys.executable, "-c", c["command"][2]], capture_output=True, text=True, env={}, timeout=10)
        self.assertEqual(r.returncode, 1)
        self.assertIn("WHISKY_DB_URL is not set", r.stdout)

    def test_missing_settings_stop_before_anything_is_printed(self):
        with self.assertRaises(SystemExit):
            sentinel_manifests.manifests({"HARNESS": "h"})


if __name__ == "__main__":
    unittest.main()
