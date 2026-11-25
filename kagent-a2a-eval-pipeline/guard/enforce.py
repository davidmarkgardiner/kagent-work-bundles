#!/usr/bin/env python3
"""Guard enforcement: apply a block policy that propose.py wrote, but only when it is definitely bad, and with hard limits.

Chosen design (owner decision, 24 Nov 2026): a definite offender is blocked immediately and the policy is applied directly to the cluster, as a failsafe.
Because that is a real power, every call is gated, and nothing here is automatic unless the caller passes --auto-apply AND --context:

- only signals in rules.yaml `autoApply.signals` (default: forbidden_tool, a deterministic tool-outside-allowlist result); token burn and the rest stay ticket-only;
- the policy file is RE-VALIDATED here, independently of propose.py: one named HTTPRoute, action Deny, one `jwt.sub` identifier, the allowed namespace, a guard-deny- name;
- the never-block list is checked again; a hard cap on active guard blocks (`autoApply.maxActiveBlocks`) stops a runaway Guard from blocking the fleet;
- a per-hour cap and a kill switch (`guard-enforce.disabled` file or GUARD_ENFORCE_DISABLED=1);
- server dry-run first, then apply, then read back; every decision is one ledger line; a block stays until a person runs `release` (it never expires by itself).
`release` removes only policies this tool applied. Exit: 0 ok | 1 something refused | 3 bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

SUBJECT = re.compile(r"^[A-Za-z0-9._:@/-]{1,128}$")
NAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
EXPR = re.compile(r'^jwt\.sub == "([A-Za-z0-9._:@/-]{1,128})"$')
LABEL = "app.kubernetes.io/managed-by"
OWNER = "guard-proposal"


def kubectl(ctx: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["kubectl", "--context", ctx, *args], capture_output=True, text=True, input=stdin)


def validate(pol: dict[str, Any], rules: dict[str, Any], agent: str | None = None) -> tuple[str | None, str]:
    """Return (subject or None, reason). Independent of propose.py on purpose."""
    try:
        md, spec = pol["metadata"], pol["spec"]
        if pol.get("kind") != "AgentgatewayPolicy" or pol.get("apiVersion") != "agentgateway.dev/v1alpha1":
            return None, "not an AgentgatewayPolicy v1alpha1"
        if not str(md.get("name", "")).startswith("guard-deny-") or not NAME.fullmatch(md["name"]):
            return None, "name must be guard-deny-<slug>"
        if md.get("namespace") != rules.get("policyNamespace"):
            return None, "namespace is not the allowed policy namespace"
        if (md.get("labels") or {}).get(LABEL) != OWNER:
            return None, "missing the guard managed-by label"
        refs = spec["targetRefs"]
        if len(refs) != 1 or refs[0].get("kind") != "HTTPRoute" or not NAME.fullmatch(str(refs[0].get("name", ""))):
            return None, "must target exactly one named HTTPRoute"
        if set(spec) != {"targetRefs", "traffic"} or set(spec["traffic"]) != {"authorization"}:
            return None, "unexpected fields in spec"
        auth = spec["traffic"]["authorization"]
        exprs = auth["policy"]["matchExpressions"]
        if auth.get("action") != "Deny" or len(exprs) != 1 or set(auth) != {"action", "policy"} or set(auth["policy"]) != {"matchExpressions"}:
            return None, "must be a single-expression Deny"
        m = EXPR.fullmatch(exprs[0])
        if not m or not SUBJECT.fullmatch(m.group(1)):
            return None, "expression is not exactly jwt.sub == \"<plain identifier>\""
        subject = m.group(1)
    except (KeyError, TypeError, AttributeError):
        return None, "policy is malformed"
    deny = [str(n).lower() for n in rules.get("neverBlock") or []]
    for n in filter(None, (subject, refs[0]["name"], md["name"], agent)):  # the AGENT is checked too: a policy name never matches the never-block prefixes
        low = str(n).lower()
        if any(low == d or low.startswith(d + "-") for d in deny):
            return None, f"{n!r} is on the never-block list"
    return subject, "ok"


def ledger_append(path: Path | None, rec: dict[str, Any]) -> None:
    if path:
        with open(path, "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")


def recent_applies(path: Path | None, now: float, window: int = 3600) -> int:
    n = 0
    if path and path.exists():
        for line in path.read_text().splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("outcome") in ("applied", "applied_unverified") and now - d.get("epoch", 0) < window:
                n += 1
    return n


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--proposals", type=Path, required=True, help="the proposals.json that propose.py wrote (its policy files sit beside it)")
    a.add_argument("--rules", type=Path, default=Path(__file__).with_name("rules.yaml"))
    a.add_argument("--findings", type=Path, required=True, help="the detector output (guard/detect.py): the ONLY source of what was found")
    a.add_argument("--identity-map", type=Path, required=True, help="the trusted subject/route map: the ONLY source of who may be blocked")
    a.add_argument("--context"); a.add_argument("--auto-apply", action="store_true"); a.add_argument("--ledger", type=Path, required=True, help="required: it carries the hourly cap")
    r = sub.add_parser("release")
    r.add_argument("--context", required=True); r.add_argument("--namespace", required=True); r.add_argument("--name", required=True); r.add_argument("--ledger", type=Path)
    args = ap.parse_args()
    # A caller-supplied clock would defeat the hourly cap, so time is only overridable in test mode.
    now = float(os.environ["GUARD_TEST_NOW"]) if os.environ.get("GUARD_TEST_MODE") == "1" and os.environ.get("GUARD_TEST_NOW") else time.time()

    if args.cmd == "release":
        g = kubectl(args.context, "-n", args.namespace, "get", "agentgatewaypolicies.agentgateway.dev", args.name, "-o", "json")
        if g.returncode != 0:
            print(json.dumps({"outcome": "not_found", "detail": g.stderr.strip()[:200]})); return 1
        if (json.loads(g.stdout)["metadata"].get("labels") or {}).get(LABEL) != OWNER:
            print(json.dumps({"outcome": "refused_not_guard_managed"})); return 1
        d = kubectl(args.context, "-n", args.namespace, "delete", "agentgatewaypolicies.agentgateway.dev", args.name)
        ledger_append(args.ledger, {"epoch": now, "policy": args.name, "outcome": "released" if d.returncode == 0 else "release_failed"})
        print(json.dumps({"outcome": "released" if d.returncode == 0 else "release_failed", "detail": (d.stdout + d.stderr).strip()[:200]}))
        return 0 if d.returncode == 0 else 1

    if not args.auto_apply or not args.context:
        print(json.dumps({"outcome": "refused", "reason": "needs --auto-apply and an explicit --context; nothing was applied"})); return 1
    try:
        rules = yaml.safe_load(args.rules.read_text())
        props = json.loads(args.proposals.read_text())["results"]
        findings = {f["dedupe_key"]: f for f in json.loads(args.findings.read_text())["findings"]}
        idmap = yaml.safe_load(args.identity_map.read_text()) or {}
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr); return 3
    cfg = rules.get("autoApply") or {}
    out, rc = [], 0
    import fcntl
    if args.ledger.exists():
        for line in args.ledger.read_text().splitlines():
            if line.strip():
                try:
                    json.loads(line)
                except ValueError:
                    print(json.dumps({"outcome": "refused", "reason": "ledger is corrupt; failing closed so the cap cannot be silently bypassed"})); return 1
    lock = open(str(args.ledger) + ".lock", "a"); fcntl.flock(lock, fcntl.LOCK_EX)  # one enforcer at a time: the caps are check-then-apply
    def killed() -> bool:  # checked per proposal, in every place an operator might have put it
        return os.environ.get("GUARD_ENFORCE_DISABLED", "").lower() in ("1", "true", "yes") or any((d / "guard-enforce.disabled").exists() for d in (args.proposals.parent, args.ledger.parent, args.rules.parent))
    for p in props:
        rec: dict[str, Any] = {"epoch": now, "finding": p.get("finding"), "signal": p.get("signal"), "agent": p.get("agent")}
        def done(outcome: str, reason: str = "") -> None:
            nonlocal rc
            rec.update(outcome=outcome, reason=reason); out.append(rec); ledger_append(args.ledger, rec)
            rc = rc or (0 if outcome in ("applied", "skipped_not_a_block", "already_applied") else 1)
        if not p.get("policy_file"):
            done("skipped_not_a_block"); continue
        if killed():
            done("refused", "kill switch"); continue
        f = findings.get(p.get("finding"))  # the signal and agent come from the detector's finding, never from the editable proposal
        if not f:
            done("refused", "no matching detector finding for this proposal"); continue
        rec["signal"], rec["agent"] = f["signal"], f.get("agent")
        if f.get("source") not in (cfg.get("autoApplySources") or ["receipt", "run"]):
            done("refused", f"finding source {f.get('source')!r} cannot auto-block: a trace can mix agents, so its attribution is not trusted (proposal only)"); continue
        if f["signal"] not in (cfg.get("signals") or []):
            done("refused", f"signal {f['signal']!r} is not in autoApply.signals (ticket only)"); continue
        try:
            pol = yaml.safe_load((args.proposals.parent / p["policy_file"]).read_text())
        except (OSError, yaml.YAMLError):
            done("refused", "policy file unreadable"); continue
        subject, why = validate(pol, rules, f.get("agent"))
        if not subject:
            done("refused", f"re-validation failed: {why}"); continue
        ns, name = pol["metadata"]["namespace"], pol["metadata"]["name"]
        rec.update(policy=name, subject=subject, route=pol["spec"]["targetRefs"][0]["name"])
        m = (idmap.get("agents") or {}).get(f.get("agent"))
        if not m or m.get("subject") != subject or m.get("route") != rec["route"] or (m.get("namespace") or rules.get("policyNamespace")) != ns:
            done("refused", "the policy does not match the trusted identity map for this agent"); continue
        lst = kubectl(args.context, "-n", ns, "get", "agentgatewaypolicies.agentgateway.dev", "-l", f"{LABEL}={OWNER}", "-o", "json")
        if lst.returncode != 0:
            done("refused", "cannot count existing guard blocks; failing closed"); continue
        active = [i for i in json.loads(lst.stdout).get("items", []) if (i["metadata"].get("annotations") or {}).get("guard.kagent.dev/applied") == "true"]
        def _recent(i: dict[str, Any]) -> bool:
            try:
                return now - datetime.fromisoformat(i["metadata"]["annotations"]["guard.kagent.dev/applied-at"]).timestamp() < 3600
            except (KeyError, ValueError, TypeError):
                return False
        # The cap is counted on the cluster as well as in the ledger, so a fresh or different --ledger cannot reset it.
        if max(recent_applies(args.ledger, now), sum(1 for i in active if _recent(i))) >= int(cfg.get("maxAppliesPerHour", 2)):
            done("refused", "hourly apply cap reached; a person must decide"); continue
        if name in {i.get("metadata", {}).get("name") for i in active}:
            done("already_applied", "this block is already active; nothing re-applied and no cap slot used"); continue
        if len(active) >= int(cfg.get("maxActiveBlocks", 3)):
            done("refused", f"{len(active)} guard blocks are already active (cap {cfg.get('maxActiveBlocks', 3)}); a person must review"); continue
        pol["metadata"].setdefault("annotations", {}).update({"guard.kagent.dev/applied": "true", "guard.kagent.dev/applied-at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                                               "guard.kagent.dev/review-by": (datetime.fromtimestamp(now, timezone.utc) + timedelta(days=int(cfg.get("reviewDays", 1)))).isoformat(),
                                               "guard.kagent.dev/note": "Applied automatically by the Guard for a definite offence. Never expires by itself: a person reviews, fixes, then runs `enforce.py release`."})
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            yaml.safe_dump(pol, tf, sort_keys=False); path = tf.name
        dry = kubectl(args.context, "apply", "--dry-run=server", "-f", path)
        if dry.returncode != 0:
            done("refused", "server dry-run rejected it: " + dry.stderr.strip()[:200]); continue
        ap_ = kubectl(args.context, "apply", "-f", path)
        chk = kubectl(args.context, "-n", ns, "get", "agentgatewaypolicies.agentgateway.dev", name, "-o", "name")
        if ap_.returncode != 0 and chk.returncode == 0:
            done("applied_unverified", "apply reported a failure but the object exists: treat the block as ACTIVE; it counts towards the caps"); continue
        if ap_.returncode == 0 and chk.returncode != 0:
            done("applied_unverified", "the apply succeeded but the read-back failed: treat the block as ACTIVE and check by hand; it counts towards the caps"); continue
        if ap_.returncode != 0:
            done("failed", "apply failed: " + ap_.stderr.strip()[:200]); continue
        done("applied", "definite offence; blocked until a person releases it")
    print(json.dumps({"results": out}, indent=1))
    return rc


def main() -> int:
    try:
        return _main()
    except SystemExit:
        raise
    except Exception as exc:  # fail closed and loudly rather than with a bare traceback
        print(json.dumps({"outcome": "crashed", "error": f"{type(exc).__name__}: {exc}", "note": "treat the state as unknown and check by hand"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
