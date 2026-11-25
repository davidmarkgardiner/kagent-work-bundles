"""Guard enforcement (guarded auto-apply) and the model-route probe. A fake kubectl records every call, so what would reach a cluster is proven exactly."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

B = Path(__file__).resolve().parents[1]
PY = sys.executable
FAKE = '''#!/usr/bin/env python3
import os, sys, json
d = os.environ["FAKE_DIR"]; a = sys.argv[1:]
open(d + "/calls.log", "a").write(" ".join(a) + "\\n")
if "delete" in a: sys.exit(0)
if "apply" in a:
    if "--dry-run=server" in a:
        if os.environ.get("FAKE_DRY_RC", "0") != "0": sys.stderr.write("admission webhook denied"); sys.exit(1)
        print("policy created (server dry run)"); sys.exit(0)
    if os.environ.get("FAKE_APPLY_RC", "0") != "0": sys.stderr.write("timeout"); sys.exit(1)
    print("policy created"); sys.exit(0)
if "get" in a and "-l" in a:
    if os.environ.get("FAKE_LIST_RC", "0") != "0": sys.stderr.write("forbidden"); sys.exit(1)
    print(open(d + "/active.json").read()); sys.exit(0)
if "get" in a:
    if os.environ.get("FAKE_GET_RC", "0") != "0": sys.stderr.write("not found"); sys.exit(1)
    print(open(d + "/policy.json").read() if "json" in a else "agentgatewaypolicy/x"); sys.exit(0)
sys.exit(0)
'''
FINDING = {"signal": "forbidden_tool", "source": "receipt", "agent": "sentinel-investigator", "caller": None, "id": "t1", "dedupe_key": "sentinel-investigator|forbidden_tool|1", "evidence": {"tools": ["k8s_scale"]}}
MAP = {"agents": {"sentinel-investigator": {"subject": "svc-sentinel", "route": "sentinel-a2a"}}}


def setup(findings=(FINDING,), mapping=MAP, active=()):
    d = Path(tempfile.mkdtemp())
    k = d / "bin"; k.mkdir(); (k / "kubectl").write_text(FAKE); (k / "kubectl").chmod(0o755)
    (d / "active.json").write_text(json.dumps({"items": list(active)}))
    (d / "f.json").write_text(json.dumps({"findings": list(findings)})); (d / "m.yaml").write_text(yaml.safe_dump(mapping))
    env = {**os.environ, "PATH": f"{k}:{os.environ['PATH']}", "FAKE_DIR": str(d)}
    p = subprocess.run([PY, str(B / "guard/propose.py"), "--findings", str(d / "f.json"), "--identity-map", str(d / "m.yaml"), "--out", str(d / "out"), "--now", "2026-11-24T12:00:00+00:00"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return d, env


def enforce(d, env, *extra, auto=True, ctx="lab", ledger=True, now="1000"):
    cmd = [PY, str(B / "guard/enforce.py"), "apply", "--proposals", str(d / "out/proposals.json"), "--findings", str(d / "f.json"), "--identity-map", str(d / "m.yaml")]
    if ledger:
        cmd += ["--ledger", str(d / "ledger.jsonl")]
    env = {**env, "GUARD_TEST_MODE": "1", "GUARD_TEST_NOW": now}
    if auto:
        cmd += ["--auto-apply"]
    if ctx:
        cmd += ["--context", ctx]
    r = subprocess.run(cmd + list(extra), capture_output=True, text=True, env=env)
    try:
        return r, json.loads(r.stdout)["results"] if r.stdout.strip().startswith("{") and "results" in r.stdout else None
    except ValueError:
        return r, None


def calls(d):
    f = d / "calls.log"
    return f.read_text().splitlines() if f.exists() else []


class Enforce(unittest.TestCase):
    def test_applies_a_definite_offence_with_dry_run_first_then_apply_then_readback(self):
        d, env = setup()
        r, res = enforce(d, env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(res[0]["outcome"], "applied")
        c = calls(d)
        self.assertIn("--dry-run=server", c[1])
        self.assertTrue(all(x.startswith("--context lab") for x in c))
        self.assertEqual(sum(1 for x in c if " apply " in f" {x} " and "--dry-run=server" not in x), 1)
        led = [json.loads(x) for x in (d / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual((led[0]["outcome"], led[0]["subject"], led[0]["route"]), ("applied", "svc-sentinel", "sentinel-a2a"))

    def test_refuses_without_auto_apply_or_without_an_explicit_context_and_calls_nothing(self):
        d, env = setup()
        for kw in ({"auto": False}, {"ctx": None}):
            r, _ = enforce(d, env, **kw)
            self.assertEqual(r.returncode, 1); self.assertIn("nothing was applied", r.stdout)
        self.assertEqual(calls(d), [])

    def test_token_burn_stays_proposal_only(self):
        f = dict(FINDING, signal="token_burn", dedupe_key="x|token_burn|1")
        d, env = setup([f])
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("ticket only", res[0]["reason"])
        self.assertEqual(calls(d), [])

    def test_a_tampered_policy_file_is_refused_by_independent_revalidation(self):
        tampers = {"two targets": lambda p: p["spec"]["targetRefs"].append({"group": "g", "kind": "HTTPRoute", "name": "other"}),
                   "allow not deny": lambda p: p["spec"]["traffic"]["authorization"].update(action="Allow"),
                   "broad expression": lambda p: p["spec"]["traffic"]["authorization"]["policy"].update(matchExpressions=['jwt.sub != ""']),
                   "injection": lambda p: p["spec"]["traffic"]["authorization"]["policy"].update(matchExpressions=['jwt.sub == "x" || true']),
                   "wrong namespace": lambda p: p["metadata"].update(namespace="kube-system"),
                   "extra field": lambda p: p["spec"]["traffic"].update(rateLimit={}),
                   "never-block subject": lambda p: p["spec"]["traffic"]["authorization"]["policy"].update(matchExpressions=['jwt.sub == "observability-agent"'])}
        for name, fn in tampers.items():
            d, env = setup()
            pf = next((d / "out").glob("policy-*.yaml")); pol = yaml.safe_load(pf.read_text()); fn(pol); pf.write_text(yaml.safe_dump(pol))
            r, res = enforce(d, env)
            self.assertEqual(res[0]["outcome"], "refused", name); self.assertIn("re-validation", res[0]["reason"], name)
            self.assertFalse([c for c in calls(d) if "apply" in c], name)

    def test_active_block_cap_stops_a_runaway_guard_blocking_the_fleet(self):
        act = [{"metadata": {"annotations": {"guard.kagent.dev/applied": "true"}}} for _ in range(3)]
        d, env = setup(active=act)
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("already active", res[0]["reason"])
        self.assertFalse([c for c in calls(d) if "apply" in c])

    def test_unreadable_cluster_state_fails_closed(self):
        d, env = setup(); env["FAKE_LIST_RC"] = "1"
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("failing closed", res[0]["reason"])

    def test_hourly_cap(self):
        d, env = setup()
        (d / "ledger.jsonl").write_text("\n".join(json.dumps({"epoch": 990, "outcome": "applied"}) for _ in range(2)) + "\n")
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("hourly apply cap", res[0]["reason"])

    def test_kill_switch(self):
        d, env = setup(); (d / "out" / "guard-enforce.disabled").write_text("")
        self.assertEqual(enforce(d, env)[1][0]["reason"], "kill switch")
        d2, env2 = setup(); env2["GUARD_ENFORCE_DISABLED"] = "1"
        self.assertEqual(enforce(d2, env2)[1][0]["reason"], "kill switch")

    def test_a_rejected_dry_run_means_no_real_apply(self):
        d, env = setup(); env["FAKE_DRY_RC"] = "1"
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("dry-run rejected", res[0]["reason"])
        self.assertEqual([c for c in calls(d) if "apply" in c and "--dry-run=server" not in c], [])

    def test_the_applied_policy_is_marked_applied_with_a_review_date_and_no_expiry(self):
        d, env = setup(); enforce(d, env)
        line = next(c for c in calls(d) if " apply -f " in f" {c} " and "--dry-run=server" not in c)
        pol = yaml.safe_load(Path(line.split("-f ")[1].strip()).read_text())
        ann = pol["metadata"]["annotations"]
        self.assertEqual(ann["guard.kagent.dev/applied"], "true")
        self.assertIn("guard.kagent.dev/review-by", ann); self.assertIn("never expires by itself", ann["guard.kagent.dev/note"].lower())
        self.assertFalse([k for k in ann if "expire" in k.lower() and "never" not in ann[k].lower() and k != "guard.kagent.dev/note"])

    def test_release_removes_only_guard_managed_policies(self):
        d, env = setup()
        (d / "policy.json").write_text(json.dumps({"metadata": {"labels": {"app.kubernetes.io/managed-by": "guard-proposal"}}}))
        r = subprocess.run([PY, str(B / "guard/enforce.py"), "release", "--context", "lab", "--namespace", "agentgateway-system", "--name", "guard-deny-x", "--ledger", str(d / "ledger.jsonl")], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout); self.assertTrue([c for c in calls(d) if " delete " in f" {c} "])
        (d / "calls.log").write_text("")
        (d / "policy.json").write_text(json.dumps({"metadata": {"labels": {"team": "someone-else"}}}))
        r = subprocess.run([PY, str(B / "guard/enforce.py"), "release", "--context", "lab", "--namespace", "agentgateway-system", "--name", "important", "--ledger", str(d / "ledger.jsonl")], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1); self.assertIn("refused_not_guard_managed", r.stdout)
        self.assertFalse([c for c in calls(d) if " delete " in f" {c} "])


class EnforceReview(unittest.TestCase):
    """Peer review round 1: enforcement must trust the detector and the identity map, never the editable proposal."""

    def test_a_tampered_proposal_signal_cannot_promote_a_ticket_only_finding_to_a_block(self):
        d, env = setup([dict(FINDING, signal="token_burn", dedupe_key="x|token_burn|1")])
        pj = d / "out/proposals.json"; doc = json.loads(pj.read_text()); doc["results"][0]["signal"] = "forbidden_tool"; pj.write_text(json.dumps(doc))
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("ticket only", res[0]["reason"])
        self.assertFalse([c for c in calls(d) if "apply" in c])

    def test_a_policy_naming_a_different_subject_or_route_than_the_identity_map_is_refused(self):
        for mutate in (lambda p: p["spec"]["traffic"]["authorization"]["policy"].update(matchExpressions=['jwt.sub == "someone-else"']),
                       lambda p: p["spec"]["targetRefs"][0].update(name="another-route")):
            d, env = setup()
            pf = next((d / "out").glob("policy-*.yaml")); pol = yaml.safe_load(pf.read_text()); mutate(pol); pf.write_text(yaml.safe_dump(pol))
            r, res = enforce(d, env)
            self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("trusted identity map", res[0]["reason"])
            self.assertFalse([c for c in calls(d) if "apply" in c])

    def test_a_proposal_with_no_matching_detector_finding_is_refused(self):
        d, env = setup()
        pj = d / "out/proposals.json"; doc = json.loads(pj.read_text()); doc["results"][0]["finding"] = "invented|forbidden_tool|9"; pj.write_text(json.dumps(doc))
        r, res = enforce(d, env)
        self.assertIn("no matching detector finding", res[0]["reason"])

    def test_the_ledger_is_required(self):
        d, env = setup()
        r, _ = enforce(d, env, ledger=False)
        self.assertEqual(r.returncode, 2); self.assertEqual(calls(d), [])

    def test_a_corrupt_ledger_fails_closed(self):
        d, env = setup(); (d / "ledger.jsonl").write_text("{not json\n")
        r, _ = enforce(d, env)
        self.assertEqual(r.returncode, 1); self.assertIn("corrupt", r.stdout); self.assertFalse([c for c in calls(d) if "apply" in c])

    def test_the_clock_cannot_be_overridden_outside_test_mode(self):
        d, env = setup()
        (d / "ledger.jsonl").write_text("\n".join(json.dumps({"epoch": time.time() - 10, "outcome": "applied"}) for _ in range(2)) + "\n")
        env2 = {k: v for k, v in env.items() if not k.startswith("GUARD_TEST")}; env2["GUARD_TEST_NOW"] = "1"  # ignored without GUARD_TEST_MODE
        r = subprocess.run([PY, str(B / "guard/enforce.py"), "apply", "--proposals", str(d / "out/proposals.json"), "--findings", str(d / "f.json"), "--identity-map", str(d / "m.yaml"),
                            "--ledger", str(d / "ledger.jsonl"), "--auto-apply", "--context", "lab"], capture_output=True, text=True, env=env2)
        self.assertIn("hourly apply cap", r.stdout)

    def test_a_repeat_apply_is_idempotent_and_uses_no_cap_slot(self):
        d, env = setup()
        pf = next((d / "out").glob("policy-*.yaml")); name = yaml.safe_load(pf.read_text())["metadata"]["name"]
        (d / "active.json").write_text(json.dumps({"items": [{"metadata": {"name": name, "annotations": {"guard.kagent.dev/applied": "true"}}}]}))
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "already_applied"); self.assertEqual(r.returncode, 0)
        self.assertFalse([c for c in calls(d) if " apply " in f" {c} "])

    def test_an_apply_whose_readback_fails_is_recorded_as_active_and_counts_towards_the_cap(self):
        d, env = setup(); env["FAKE_GET_RC"] = "1"
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "applied_unverified"); self.assertEqual(r.returncode, 1)
        (d / "ledger.jsonl").write_text((d / "ledger.jsonl").read_text() * 2)
        env.pop("FAKE_GET_RC"); r2, res2 = enforce(d, env)
        self.assertIn("hourly apply cap", res2[0]["reason"])

    def test_the_kill_switch_is_found_next_to_the_ledger_and_rules_too(self):
        for where in ("ledger", "rules"):
            d, env = setup()
            target = d if where == "ledger" else B / "guard"
            sw = target / "guard-enforce.disabled"; sw.write_text("")
            try:
                r, res = enforce(d, env)
                self.assertEqual(res[0]["reason"], "kill switch", where)
            finally:
                sw.unlink()


class EnforceRound2(unittest.TestCase):
    """Opus review, round 2."""

    def test_the_agent_name_is_checked_against_never_block_not_just_the_policy(self):
        d, env = setup()
        f = json.loads((d / "f.json").read_text()); f["findings"][0]["agent"] = "completion-evaluator"; (d / "f.json").write_text(json.dumps(f))
        m = yaml.safe_load((d / "m.yaml").read_text()); m["agents"]["completion-evaluator"] = m["agents"]["sentinel-investigator"]; (d / "m.yaml").write_text(yaml.safe_dump(m))
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("never-block", res[0]["reason"])
        self.assertFalse([c for c in calls(d) if " apply " in f" {c} " and "--dry-run=server" not in c])

    def test_a_fresh_ledger_cannot_reset_the_hourly_cap_because_the_cluster_is_counted_too(self):
        import datetime as dt
        iso = dt.datetime.fromtimestamp(990, dt.timezone.utc).isoformat()
        act = [{"metadata": {"name": f"guard-deny-other-{i}", "annotations": {"guard.kagent.dev/applied": "true", "guard.kagent.dev/applied-at": iso}}} for i in range(2)]
        d, env = setup(active=act)
        r, res = enforce(d, env)
        self.assertEqual(res[0]["outcome"], "refused"); self.assertIn("hourly apply cap", res[0]["reason"])

    def test_a_trace_sourced_or_unsourced_finding_cannot_auto_block(self):
        d, env = setup([dict(FINDING, source="otlp")])
        self.assertIn("cannot auto-block", enforce(d, env)[1][0]["reason"])
        d2, env2 = setup([{k: v for k, v in FINDING.items() if k != "source"}])
        self.assertIn("cannot auto-block", enforce(d2, env2)[1][0]["reason"])

    def test_a_trailing_newline_cannot_slip_through_the_name_checks(self):
        d, env = setup()
        pf = next((d / "out").glob("policy-*.yaml")); pol = yaml.safe_load(pf.read_text()); pol["spec"]["targetRefs"][0]["name"] = "kagent-controller\n"; pf.write_text(yaml.safe_dump(pol))
        self.assertEqual(enforce(d, env)[1][0]["outcome"], "refused")

    def test_true_and_yes_also_trip_the_kill_switch(self):
        for v in ("true", "YES"):
            d, env = setup(); env["GUARD_ENFORCE_DISABLED"] = v
            self.assertEqual(enforce(d, env)[1][0]["reason"], "kill switch", v)

    def test_an_apply_that_errors_but_persisted_is_recorded_active(self):
        d, env = setup(); env["FAKE_APPLY_RC"] = "1"
        self.assertEqual(enforce(d, env)[1][0]["outcome"], "applied_unverified")

    def test_a_policy_without_annotations_does_not_crash(self):
        d, env = setup()
        pf = next((d / "out").glob("policy-*.yaml")); pol = yaml.safe_load(pf.read_text()); pol["metadata"].pop("annotations"); pf.write_text(yaml.safe_dump(pol))
        r, res = enforce(d, env)
        self.assertNotIn("Traceback", r.stderr); self.assertIsNotNone(res)

    def test_the_same_offender_gets_the_same_policy_name_in_every_time_bucket(self):
        names = []
        for key in ("sentinel-investigator|forbidden_tool|1", "sentinel-investigator|forbidden_tool|2"):
            d, env = setup([dict(FINDING, dedupe_key=key)])
            names.append(yaml.safe_load(next((d / "out").glob("policy-*.yaml")).read_text())["metadata"]["name"])
        self.assertEqual(names[0], names[1])


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        code = {"/ok": 200, "/429": 429, "/503": 503, "/401": 401, "/400": 400}.get(self.path)
        if self.path == "/slow":
            time.sleep(3); code = 200
        self.send_response(code or 404)
        if code == 429:
            self.send_header("Retry-After", "7")
        self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")


class Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_probe(self, path, **env):
        r = subprocess.run([PY, str(B / "guard/model_probe.py"), "--url", self.base + path, "--model", "m", "--timeout", "1"], capture_output=True, text=True, env={**os.environ, **env})
        return r.returncode, json.loads(r.stdout) if r.stdout.strip() else None

    def test_classification_and_exit_codes(self):
        for path, kind, rc in (("/ok", "ok", 0), ("/429", "rate_limited", 2), ("/503", "server_error", 2), ("/401", "auth", 1), ("/400", "refused", 1), ("/slow", "timeout", 2)):
            code, out = self.run_probe(path)
            self.assertEqual((out["kind"], code), (kind, rc), path)
        self.assertEqual(self.run_probe("/429")[1]["retry_after_s"], 7.0)

    def test_connection_refused_and_unresolvable_host_are_a_wait_not_a_refusal(self):
        r = subprocess.run([PY, str(B / "guard/model_probe.py"), "--url", "http://127.0.0.1:9/x", "--model", "m", "--timeout", "1"], capture_output=True, text=True)
        self.assertEqual((json.loads(r.stdout)["kind"], r.returncode), ("connect", 2))
        r = subprocess.run([PY, str(B / "guard/model_probe.py"), "--url", "http://no-such-host.invalid/x", "--model", "m", "--timeout", "2"], capture_output=True, text=True)
        self.assertIn(json.loads(r.stdout)["kind"], ("dns", "connect")); self.assertEqual(r.returncode, 2)

    def test_the_key_comes_from_an_environment_variable_and_is_never_printed(self):
        r = subprocess.run([PY, str(B / "guard/model_probe.py"), "--url", self.base + "/ok", "--model", "m", "--api-key-env", "PROBE_KEY"], capture_output=True, text=True, env={**os.environ, "PROBE_KEY": "sekret-123"})
        self.assertEqual(r.returncode, 0); self.assertNotIn("sekret-123", r.stdout + r.stderr)
        r = subprocess.run([PY, str(B / "guard/model_probe.py"), "--url", self.base + "/ok", "--model", "m", "--api-key-env", "NOT_SET_ANYWHERE"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
