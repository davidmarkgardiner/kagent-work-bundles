"""Replays of real kagent 1.x runs from the VM 201 lab (24 Nov 2026), sanitized: the Sentinel worker passing Warden under the
ordered-steps prompt, a deliberately misbehaving worker, and the Guard agent's ticket gated by its own contract."""

from __future__ import annotations

import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

B = Path(__file__).resolve().parents[1]
FX = B / "tests" / "fixtures"


def load(name, rel):
    s = importlib.util.spec_from_file_location(name, B / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


vc, det = load("vc_live", "verify_completion.py"), load("det_live", "guard/detect.py")
rec = lambda n: json.loads((FX / n).read_text())
SENT = vc.load_contract(B / "completion-gate/contracts/sentinel-investigator.yaml")
GUARD = vc.load_contract(B / "completion-gate/contracts/guard.yaml")
RULES = yaml.safe_load((B / "guard/rules.yaml").read_text())
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)


class LiveReplay(unittest.TestCase):
    def test_sentinel_worker_passes_warden(self):
        r = vc.verify(SENT, rec("a2a-v1x-sentinel-pass-live.json"))
        self.assertEqual((r["verdict"], r["route"]), ("PASS", "ticket"), r["failures"])

    def test_rogue_worker_is_rejected_for_exactly_its_extra_tool(self):
        r = vc.verify(SENT, rec("a2a-v1x-rogue-extra-tool-live.json"))
        self.assertEqual((r["verdict"], r["route"]), ("FAIL", "reject"))
        self.assertEqual(r["failures"], ["tool not in allowedTools: k8s_get_available_api_resources"])

    def test_guard_ticket_passes_its_own_contract_with_exact_dedupe_key(self):
        r = vc.verify(GUARD, rec("a2a-v1x-guard-ticket-live.json"))
        self.assertEqual((r["verdict"], r["route"]), ("PASS", "ticket"), r["failures"])
        self.assertIn("sentinel-investigator|forbidden_tool|", r["approved_output"])
        self.assertNotIn("has been blocked", r["approved_output"].lower().replace("nothing has been blocked", ""))

    def test_guard_detector_on_real_receipts(self):
        ev = lambda n: det.load_events(FX / n, "sentinel-investigator")
        ok = det.evaluate(ev("a2a-v1x-sentinel-pass-live.json"), RULES, NOW, [])
        self.assertEqual(ok["status"], "clean", ok)
        bad = det.evaluate(ev("a2a-v1x-rogue-extra-tool-live.json"), RULES, NOW)
        self.assertEqual([f["signal"] for f in bad["findings"]], ["forbidden_tool"])
        self.assertEqual(bad["findings"][0]["evidence"]["tools"], ["k8s_get_available_api_resources"])


if __name__ == "__main__":
    unittest.main()
