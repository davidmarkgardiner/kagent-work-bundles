"""guard/remediate.py: the overseer's fix-it step. A stateful fake kubectl holds the agent, so every switch, refusal and revert is checked exactly."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

B = Path(__file__).resolve().parents[1]
PY = sys.executable
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_DIR"]; a = sys.argv[1:]
open(d + "/calls.log", "a").write(" ".join(a) + "\n")
agent_p = d + "/agent.json"
def load(): return json.load(open(agent_p))
if "patch" in a:
    if "--dry-run=server" in a:
        if os.environ.get("FAKE_DRY_RC", "0") != "0": sys.stderr.write("admission denied"); sys.exit(1)
        sys.exit(0)
    p = json.loads(a[a.index("-p") + 1]); ag = load()
    mc = p["spec"]["template"]["inline"]["modelConfig"]["name"]
    ag["spec"]["template"]["inline"]["modelConfig"]["name"] = mc
    ann = ag["metadata"].setdefault("annotations", {})
    for k, v in (p.get("metadata", {}).get("annotations") or {}).items():
        if v is None: ann.pop(k, None)
        else: ann[k] = v
    ag["metadata"]["generation"] = ag["metadata"].get("generation", 1) + 1
    ready = os.environ.get("FAKE_READY", "1") == "1"
    ag["status"] = {"conditions": [{"type": "Ready", "status": "True" if ready else "False", "observedGeneration": ag["metadata"]["generation"]}]}
    json.dump(ag, open(agent_p, "w")); sys.exit(0)
if "get" in a and "modelconfig" in a:
    name = a[a.index("modelconfig") + 1]
    print(json.load(open(d + "/models.json")).get(name, "")); sys.exit(0)
if "get" in a and "agents" in a:
    print(json.dumps({"items": [load()] + json.load(open(d + "/peers.json"))})); sys.exit(0)
if "get" in a and "agent" in a:
    print(json.dumps(load())); sys.exit(0)
sys.exit(0)
'''
CFG = {"namespace": "kagent", "triggerKinds": ["rate_limited", "server_error", "timeout", "connect"], "maxSwitchesPerHour": 2,
       "perAgentCooldownS": 3600, "readbackTimeoutS": 2, "neverTouch": ["guard-agent"],
       "agents": {"worker": {"primary": "primary-mc", "fallbacks": ["fallback-mc"]}, "guard-agent": {"primary": "primary-mc", "fallbacks": ["fallback-mc"]}}}
MODELS = {"primary-mc": "model-a", "fallback-mc": "model-b"}


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def setup(name="worker", mc="primary-mc", annotations=None, peers=(), cfg=None):
    d = Path(tempfile.mkdtemp())
    k = d / "bin"; k.mkdir(); (k / "kubectl").write_text(FAKE); (k / "kubectl").chmod(0o755)
    agent = {"metadata": {"name": name, "generation": 1, "annotations": annotations or {}},
             "spec": {"template": {"inline": {"modelConfig": {"name": mc}}}},
             "status": {"conditions": [{"type": "Ready", "status": "True", "observedGeneration": 1}]}}
    (d / "agent.json").write_text(json.dumps(agent)); (d / "peers.json").write_text(json.dumps(list(peers)))
    (d / "models.json").write_text(json.dumps(MODELS)); (d / "fb.yaml").write_text(yaml.safe_dump(cfg or CFG))
    (d / "p1.json").write_text(json.dumps({"model": "model-a", "kind": "rate_limited", "http": 429}))
    (d / "p2.json").write_text(json.dumps({"model": "model-b", "kind": "ok", "http": 200}))
    env = {**os.environ, "PATH": f"{k}:{os.environ['PATH']}", "FAKE_DIR": str(d)}
    env.pop("GUARD_REMEDIATE_DISABLED", None)
    return d, env


def run(d, env, cmd="apply", agent="worker", **kw):
    args = [PY, str(B / "guard/remediate.py"), cmd, "--agent", agent, "--context", "lab", "--fallbacks", str(d / "fb.yaml"), "--ledger", str(d / "ledger.jsonl")]
    if cmd == "apply":
        args += ["--probe", str(d / "p1.json"), "--fallback-probe", str(d / "p2.json"), "--out", str(d / "out")]
    p = subprocess.run(args, capture_output=True, text=True, env={**env, **kw})
    out = json.loads(p.stdout or p.stderr or "{}")
    return p.returncode, out


def agent(d):
    return json.loads((d / "agent.json").read_text())


def patched(d):
    return [l for l in (d / "calls.log").read_text().splitlines() if " patch " in f" {l} " and "--dry-run=server" not in l] if (d / "calls.log").exists() else []


class Remediate(unittest.TestCase):
    def test_switches_on_429_reads_back_and_writes_ticket(self):
        d, env = setup()
        rc, out = run(d, env)
        self.assertEqual((rc, out["decision"], out["to"]), (0, "switched", "fallback-mc"))
        a = agent(d)
        self.assertEqual(a["spec"]["template"]["inline"]["modelConfig"]["name"], "fallback-mc")
        self.assertEqual(a["metadata"]["annotations"]["guard.kagent.dev/remediated-from"], "primary-mc")
        self.assertIn("rate_limited", (d / "out/remediation-worker.md").read_text())
        self.assertEqual(json.loads((d / "ledger.jsonl").read_text().splitlines()[-1])["decision"], "switched")

    def test_auth_and_refused_errors_go_to_a_person(self):
        for kind in ("auth", "refused", "dns", "ok"):
            d, env = setup()
            (d / "p1.json").write_text(json.dumps({"model": "model-a", "kind": kind, "http": 401}))
            rc, out = run(d, env)
            self.assertEqual((rc, out["decision"]), (1, "refused"), kind)
            self.assertEqual(patched(d), [], kind)

    def test_fallback_must_probe_ok(self):
        d, env = setup()
        (d / "p2.json").write_text(json.dumps({"model": "model-b", "kind": "rate_limited", "http": 429}))
        self.assertEqual(run(d, env)[1]["decision"], "refused")
        self.assertEqual(patched(d), [])

    def test_probe_must_test_the_modelconfig_it_claims(self):
        d, env = setup()
        (d / "p1.json").write_text(json.dumps({"model": "some-other-model", "kind": "rate_limited", "http": 429}))
        rc, out = run(d, env)
        self.assertIn("does not match", out["reason"])
        self.assertEqual(patched(d), [])

    def test_unlisted_and_never_touch_agents_refused(self):
        d, env = setup(name="stranger")
        self.assertIn("not in fallbacks", run(d, env, agent="stranger")[1]["reason"])
        d, env = setup(name="guard-agent")
        self.assertIn("never-touch", run(d, env, agent="guard-agent")[1]["reason"])

    def test_unknown_current_modelconfig_refused(self):
        d, env = setup(mc="someone-elses-mc")
        self.assertIn("not listed", run(d, env)[1]["reason"])

    def test_cooldown_refuses_a_second_switch(self):
        d, env = setup(annotations={"guard.kagent.dev/remediated-at": iso(time.time() - 60)})
        self.assertIn("cooldown", run(d, env)[1]["reason"])
        self.assertEqual(patched(d), [])

    def test_unreadable_timestamp_counts_as_recent(self):
        d, env = setup(annotations={"guard.kagent.dev/remediated-at": "yesterday"})
        self.assertIn("cooldown", run(d, env)[1]["reason"])

    def test_hourly_cap_counts_cluster_annotations_when_ledger_is_lost(self):
        recent = {"metadata": {"name": "p", "annotations": {"guard.kagent.dev/remediated-at": iso(time.time() - 120)}}}
        d, env = setup(peers=[recent, recent])
        self.assertIn("hourly switch cap", run(d, env)[1]["reason"])
        self.assertEqual(patched(d), [])

    def test_kill_switch(self):
        d, env = setup()
        self.assertIn("kill switch", run(d, env, GUARD_REMEDIATE_DISABLED="1")[1]["reason"])
        d, env = setup()
        (d / "guard-remediate.disabled").write_text("")
        self.assertIn("kill switch", run(d, env)[1]["reason"])
        self.assertEqual(patched(d), [])

    def test_server_dry_run_refusal_stops_before_any_change(self):
        d, env = setup()
        rc, out = run(d, env, FAKE_DRY_RC="1")
        self.assertIn("dry-run", out["reason"])
        self.assertEqual(patched(d), [])

    def test_not_ready_after_switch_is_reverted(self):
        d, env = setup()
        rc, out = run(d, env, FAKE_READY="0")
        self.assertEqual((rc, out["decision"]), (1, "reverted_not_ready"))
        self.assertEqual(agent(d)["spec"]["template"]["inline"]["modelConfig"]["name"], "primary-mc")
        self.assertNotIn("guard.kagent.dev/remediated-from", agent(d)["metadata"]["annotations"])

    def test_revert_restores_primary_only_after_a_recorded_switch(self):
        d, env = setup()
        self.assertEqual(run(d, env, cmd="revert")[1]["decision"], "refused")
        run(d, env)
        rc, out = run(d, env, cmd="revert")
        self.assertEqual((rc, out["decision"], out["to"]), (0, "reverted", "primary-mc"))
        self.assertEqual(agent(d)["spec"]["template"]["inline"]["modelConfig"]["name"], "primary-mc")

    def test_demo_config_templates_fill_and_parse(self):
        demo = B / "demo/config"
        env = {"POLICY_NS": "ns1", "GW_CALLER_NS": "c", "GW_CALLER_SA": "sa", "GW_ROUTE": "r", "NS": "kagent", "STUB_MODELCONFIG": "s", "FALLBACK_MODELCONFIG": "f"}
        import re
        for f in ("rules", "ids", "fallbacks"):
            text = re.sub(r"\$\{(\w+)\}", lambda m: env[m.group(1)], (demo / f"{f}.demo.yaml").read_text())
            doc = yaml.safe_load(text)
            self.assertIsInstance(doc, dict, f)
        self.assertEqual(yaml.safe_load(re.sub(r"\$\{(\w+)\}", lambda m: env[m.group(1)], (demo / "fallbacks.demo.yaml").read_text()))["agents"]["demo-worker"],
                         {"primary": "s", "fallbacks": ["f"]})


if __name__ == "__main__":
    unittest.main()


class DemoReplay(unittest.TestCase):
    """The live demo runs of 25 Nov 2026, replayed: the detector must give the same verdicts offline."""

    def test_live_demo_receipts(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("det_demo", B / "guard/detect.py")
        det = importlib.util.module_from_spec(spec); spec.loader.exec_module(det)
        rules = yaml.safe_load((B / "demo/config/rules.demo.yaml").read_text().replace("${POLICY_NS}", "ns"))
        now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        ok = det.evaluate(det.load_events(B / "tests/fixtures/a2a-v1x-demo-healthy-live.json", "demo-healthy"), rules, now, [])
        self.assertEqual(ok["status"], "clean", ok)
        bad = det.evaluate(det.load_events(B / "tests/fixtures/a2a-v1x-demo-rogue-delete-live.json", "demo-rogue"), rules, now, [])
        self.assertEqual([(f["signal"], f["evidence"]["tools"], f["source"]) for f in bad["findings"]],
                         [("forbidden_tool", ["k8s_delete_resource"], "receipt")])
