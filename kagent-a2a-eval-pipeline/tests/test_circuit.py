"""Spend and retry guards for the monitoring loop: a failing agent, a 429 storm or a bad alert must never become a token-burning loop."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B))
spec = importlib.util.spec_from_file_location("circuit", B / "guard/circuit.py")
cm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cm)
L = cm.load_limits(B / "guard/loop-limits.yaml")
FX = B / "tests/fixtures/a2a-v1x-overseer-400-live.json"


def circ(now=1000.0, state=None, limits=None):
    return cm.Circuit(state or Path(tempfile.mkdtemp()) / "s.json", limits or L, now)


class Guards(unittest.TestCase):
    def test_permanent_400_is_held_for_a_day_and_never_retried(self):
        c = circ()
        self.assertTrue(c.allow("a")[0]); c.start("a")
        self.assertEqual(c.record("a", False, 11000, 400), "permanent")
        for dt in (1, 600, 3600 * 12, 86399):
            c.now = 1000 + dt
            self.assertEqual(c.allow("a"), (False, "held_after_permanent_error"))
        c.now = 1000 + 86401
        self.assertEqual(c.allow("a")[1], "attempt_cap" if len([t for t in c.s["keys"]["a"]["attempts"] if c.now - t < L["windowS"]]) >= 2 else "ok")

    def test_429_backs_off_exponentially_capped_and_honours_retry_after(self):
        c = circ(); c.start("a"); c.record("a", False, 0, 429)
        self.assertEqual(c.s["keys"]["a"]["next_try"], 1000 + 60)
        c.now = 1059; self.assertEqual(c.allow("a"), (False, "rate_limited_wait"))
        c.now = 1061; self.assertTrue(c.allow("a")[0])
        c2 = circ(); c2.start("a"); c2.record("a", False, 0, 429, retry_after_s=600)
        self.assertEqual(c2.s["keys"]["a"]["next_try"], 1000 + 600)
        c3 = circ()
        for _ in range(8):
            c3.record("a", False, 0, 503)
        self.assertEqual(c3.s["keys"]["a"]["next_try"], 1000 + L["backoffCapS"])  # capped, not 60*2^7

    def test_attempt_cap_stops_a_single_alert_looping(self):
        c = circ(limits={**L, "breakerFailures": 99})
        for i in range(2):
            self.assertTrue(c.allow("a")[0]); c.start("a"); c.record("a", False, 10, 503); c.now += 100  # stays inside the 3600 s window
            c.s["keys"]["a"]["next_try"] = 0
        self.assertEqual(c.allow("a"), (False, "attempt_cap"))
        c.now += L["windowS"] + 1
        self.assertTrue(c.allow("a")[0])  # window passed

    def test_breaker_opens_after_consecutive_failures_across_alerts_and_closes_after_cooldown(self):
        c = circ()
        for k in ("a", "b", "c"):
            c.record(k, False, 100, 500)
        self.assertEqual(c.allow("fresh"), (False, "circuit_open"))
        c.now += L["cooldownS"] + 1
        self.assertTrue(c.allow("fresh")[0])

    def test_one_success_resets_the_consecutive_count(self):
        c = circ()
        c.record("a", False, 1, 500); c.record("b", False, 1, 500); c.record("c", True, 1)
        c.record("d", False, 1, 500); c.record("e", False, 1, 500)
        self.assertTrue(c.allow("fresh")[0])

    def test_token_budget_counts_failed_runs_and_rolls_off(self):
        c = circ()
        c.record("a", False, 100_000, 503); c.record("b", True, 60_000)
        self.assertEqual(c.allow("z"), (False, "token_budget_exhausted"))
        c.now += 3601
        self.assertTrue(c.allow("z")[0])

    def test_kill_switch_file_and_env(self):
        d = Path(tempfile.mkdtemp())
        c = cm.Circuit(d / "s.json", L, 1000.0)
        self.assertTrue(c.allow("a")[0])
        (d / L["killSwitchFile"]).write_text("")
        self.assertEqual(cm.Circuit(d / "s.json", L, 1000.0).allow("a"), (False, "kill_switch"))

    def test_corrupt_state_fails_closed_and_is_not_overwritten(self):
        p = Path(tempfile.mkdtemp()) / "s.json"; p.write_text("{corrupt")
        c = cm.Circuit(p, L, 1000.0)
        self.assertEqual(c.allow("a"), (False, "state_corrupt_fail_closed"))
        c.save()
        self.assertEqual(p.read_text(), "{corrupt")  # left for a person to look at
        p.write_text(json.dumps({"keys": [], "spend": {}}))  # wrong shape is corrupt too
        self.assertTrue(cm.Circuit(p, L, 1000.0).corrupt)

    def test_missing_state_is_a_fresh_start_and_saves_atomically(self):
        p = Path(tempfile.mkdtemp()) / "s.json"
        c = cm.Circuit(p, L, 1000.0); self.assertTrue(c.allow("a")[0]); c.start("a"); c.save()
        self.assertTrue(p.exists()); self.assertFalse(list(p.parent.glob("*.tmp")))

    def test_classify(self):
        self.assertEqual(cm.classify(None, 'llm error "OpenAI API error: 400 Bad Request"', L), "permanent")
        self.assertEqual(cm.classify(None, "upstream 429 too many requests", L), "retryable")
        self.assertEqual(cm.classify(None, "something odd", L), "unknown")
        self.assertEqual(cm.classify(404, None, L), "permanent")


def alert(fp):
    return {"status": "firing", "labels": {"alertname": "X"}, "annotations": {}, "fingerprint": fp, "startsAt": "2026-11-24T12:00:00Z"}


class Intake(unittest.TestCase):
    def cli(self, d, *args):
        return subprocess.run([sys.executable, str(B / "guard/alert_to_a2a.py"), *args], capture_output=True, text=True, cwd=d)

    def test_real_failed_overseer_receipt_parks_the_alert_and_stops_the_retries(self):
        d = Path(tempfile.mkdtemp()); (d / "p.json").write_text(json.dumps({"alerts": [alert("fp-1")]}))
        brk = ["--breaker", str(d / "b.json"), "--now", "1000"]
        r = self.cli(d, "--payload", str(d / "p.json"), "--out", str(d / "o1"), *brk)
        self.assertEqual(json.loads(r.stdout)["results"][0]["outcome"], "request_written")
        r = self.cli(d, "--record", str(FX), "--key", "fp-1", *brk)
        rec = json.loads(r.stdout)
        self.assertEqual((rec["ok"], rec["failure_kind"], rec["tokens"]), (False, "permanent", 11274))  # the real 400 and its real cost
        r = self.cli(d, "--payload", str(d / "p.json"), "--out", str(d / "o2"), "--breaker", str(d / "b.json"), "--now", "1100")
        self.assertEqual(json.loads(r.stdout)["results"][0]["outcome"], "withheld_held_after_permanent_error_human_notified")
        self.assertFalse(list((d / "o2").glob("request-*")))

    def test_three_failures_open_the_breaker_for_every_alert(self):
        d = Path(tempfile.mkdtemp()); brk = ["--breaker", str(d / "b.json"), "--now", "1000"]
        for k in ("a", "b", "c"):
            self.assertEqual(self.cli(d, "--record", str(FX), "--key", k, *brk).returncode, 0)
        (d / "p.json").write_text(json.dumps({"alerts": [alert("new")]}))
        r = self.cli(d, "--payload", str(d / "p.json"), "--out", str(d / "o"), "--breaker", str(d / "b.json"), "--now", "1100")
        self.assertEqual(json.loads(r.stdout)["results"][0]["outcome"], "withheld_circuit_open_human_notified")

    def test_corrupt_breaker_state_withholds_everything(self):
        d = Path(tempfile.mkdtemp()); (d / "b.json").write_text("{nope"); (d / "p.json").write_text(json.dumps({"alerts": [alert("x")]}))
        r = self.cli(d, "--payload", str(d / "p.json"), "--out", str(d / "o"), "--breaker", str(d / "b.json"))
        self.assertEqual(json.loads(r.stdout)["results"][0]["outcome"], "withheld_state_corrupt_fail_closed_human_notified")

    def test_record_needs_breaker_and_key(self):
        d = Path(tempfile.mkdtemp())
        self.assertEqual(self.cli(d, "--record", str(FX)).returncode, 3)


class RateLimitIsAWait(unittest.TestCase):
    """The software factory's lesson: quota is a wait, never 'broken'. A shared quota that fills must not look like a failing loop."""

    def test_429_pauses_every_alert_not_just_the_one_that_hit_it(self):
        c = circ(); c.start("a"); self.assertEqual(c.record("a", False, 0, 429), "rate_limited")
        c.now = 1030
        self.assertEqual(c.allow("some-other-alert"), (False, "rate_limited_wait"))
        c.now = 1000 + 61
        self.assertTrue(c.allow("some-other-alert")[0])

    def test_a_quota_wave_never_opens_the_breaker_or_counts_as_broken(self):
        c = circ()
        for k in ("a", "b", "c", "d", "e"):
            c.record(k, False, 0, 429)
        self.assertEqual(c.s["consecutive_failures"], 0)
        self.assertEqual(c.s["open_until"], 0.0)
        c.now += L["backoffCapS"] + 1
        self.assertTrue(c.allow("fresh")[0])

    def test_a_real_failure_still_opens_the_breaker(self):
        c = circ()
        for k in ("a", "b", "c"):
            c.record(k, False, 100, 500)
        self.assertEqual(c.allow("fresh"), (False, "circuit_open"))

    def test_429_found_in_error_text_is_also_a_wait(self):
        c = circ(); self.assertEqual(c.record("a", False, 0, None, "upstream said 429 too many requests"), "rate_limited")
        self.assertEqual(c.s["consecutive_failures"], 0)

    def test_retry_after_is_honoured_up_to_the_cap(self):
        c = circ(); c.record("a", False, 0, 429, retry_after_s=600)
        self.assertEqual(c.s["pause_until"], 1000 + 600)
        c2 = circ(); c2.record("a", False, 0, 429, retry_after_s=99999)
        self.assertEqual(c2.s["pause_until"], 1000 + L["backoffCapS"])

    def test_tokens_spent_on_a_rate_limited_run_still_count(self):
        c = circ(); c.record("a", False, 5000, 429)
        self.assertEqual(c.tokens_last_hour(), 5000)


class HoldLengths(unittest.TestCase):
    def test_credential_errors_are_held_6h_and_bad_requests_24h(self):
        for status, hold in ((401, 21600), (403, 21600), (400, 86400), (404, 86400)):
            c = circ(); c.record("a", False, 1, status)
            self.assertEqual(c.s["keys"]["a"]["hold_until"], 1000 + hold, status)

    def test_a_403_is_retryable_by_a_person_after_6h_but_not_before(self):
        c = circ(); c.start("a"); c.record("a", False, 1, 403)
        c.now = 1000 + 21599; self.assertEqual(c.allow("a"), (False, "held_after_permanent_error"))
        c.now = 1000 + 21601; self.assertNotEqual(c.allow("a"), (False, "held_after_permanent_error"))


class StateHygiene(unittest.TestCase):
    def test_old_keys_are_pruned_and_live_holds_kept(self):
        p = Path(tempfile.mkdtemp()) / "s.json"
        c = cm.Circuit(p, L, 1000.0)
        c.start("old"); c.start("held"); c.record("held", False, 1, 400)
        c.save(); self.assertEqual(set(json.loads(p.read_text())["keys"]), {"old", "held"})
        c2 = cm.Circuit(p, L, 1000.0 + L["windowS"] + 1); c2.save()
        self.assertEqual(set(json.loads(p.read_text())["keys"]), {"held"})  # 'old' aged out; the 24 h hold is kept

    def test_no_shared_temp_file_name_is_left_behind(self):
        p = Path(tempfile.mkdtemp()) / "s.json"; c = cm.Circuit(p, L, 1000.0); c.start("a"); c.save()
        self.assertFalse(list(p.parent.glob("*.tmp")))


class Misclassification(unittest.TestCase):
    def test_a_429_inside_a_message_does_not_override_a_real_status(self):
        self.assertEqual(cm.classify(404, "deployment web-429 not found", L), "permanent")
        c = circ(); self.assertEqual(c.record("a", False, 1, 404, "deployment web-429 not found"), "permanent")
        self.assertEqual(c.s["pause_until"], 0.0); self.assertEqual(c.s["consecutive_failures"], 1)


if __name__ == "__main__":
    unittest.main()
