#!/usr/bin/env python3
"""Guard proposals: turn detector findings into a ticket and, where allowed, a block-policy PROPOSAL.

This tool WRITES FILES ONLY. It never applies anything and holds no cluster credentials of its own. A person (or a
separate receiver with its own approval) applies a proposed policy. `--dry-run-server --context NAME` may ask the API
server to validate a proposal (`kubectl apply --dry-run=server`), which changes nothing.

Safety rules enforced in code, not in a prompt:
- the identity to block comes ONLY from --identity-map (gateway-authenticated subjects), never from event content;
- an unmapped, malformed or never-block identity gets no policy, only a ticket saying why;
- a proposed policy targets exactly one named HTTPRoute in the one allowed namespace, and denies one JWT subject;
- findings about the Guard itself or any never-block name go to a human only;
- evidence is untrusted text: it is quoted in a fence longer than any backtick run inside it, never interpreted;
- repeats within the window are suppressed by dedupe key; losing the state file means duplicates, never silence.

An expiry annotation is documentation, not enforcement: nothing removes a policy. Use --list-expired to find ones due for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

SUBJECT_RE = re.compile(r"^[A-Za-z0-9._:@/-]{1,128}$")
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:30] or "x"


def fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    f = "`" * max(3, longest + 1)
    return f"{f}json\n{text}\n{f}"


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def load_state(path: Path | None) -> dict[str, float]:
    if not path or not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        return {k: float(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except (ValueError, OSError):
        return {}  # lost or corrupt state fails open: duplicate tickets, never a suppressed incident


def never_block(rules: dict[str, Any], *names: Any) -> str | None:
    deny = {str(n).lower() for n in rules.get("neverBlock") or []}
    for n in names:
        if n is not None and (str(n).lower() in deny or any(str(n).lower().startswith(d + "-") or str(n).lower() == d for d in deny)):
            return str(n)
    return None


def build_policy(finding: dict[str, Any], mapping: dict[str, Any], rules: dict[str, Any], now: datetime, review_days: int) -> tuple[dict[str, Any] | None, str]:
    """Return (policy or None, reason). Reasons explain every refusal."""
    agent = finding.get("agent")
    if finding["signal"] not in (rules.get("blockSignals") or []):
        return None, f"signal {finding['signal']} is ticket-only"
    m = (mapping.get("agents") or {}).get(agent)
    if not m:
        return None, "no trusted identity mapped for this agent (identity-map), so nothing can be targeted safely"
    subject, route, ns = str(m.get("subject", "")), str(m.get("route", "")), str(m.get("namespace") or rules.get("policyNamespace", ""))
    if not SUBJECT_RE.match(subject):
        return None, "mapped subject is not a plain identifier"
    if not NAME_RE.match(route):
        return None, "route must be one specific lowercase name (no wildcard or empty selector)"
    if ns != rules.get("policyNamespace"):
        return None, f"namespace {ns!r} is not the allowed policy namespace"
    hit = never_block(rules, agent, subject, route)
    if hit:
        return None, f"{hit!r} is on the never-block list"
    if finding.get("caller") and str(finding["caller"]) != subject and not (finding["caller"] is None):
        return None, "the event's caller does not match the mapped subject; refusing to block a different identity"
    name = f"guard-deny-{slug(agent)}-{hashlib.sha256(f"{agent}|{subject}|{route}".encode()).hexdigest()[:8]}"
    policy = {
        "apiVersion": "agentgateway.dev/v1alpha1", "kind": "AgentgatewayPolicy",
        "metadata": {"name": name, "namespace": ns,
                     "labels": {"app.kubernetes.io/managed-by": "guard-proposal", "app.kubernetes.io/part-of": "guard"},
                     "annotations": {"guard.kagent.dev/applied": "false", "guard.kagent.dev/proposed-at": now.isoformat(),
                                     "guard.kagent.dev/review-by": (now + timedelta(days=review_days)).isoformat(),
                                     "guard.kagent.dev/finding": finding["dedupe_key"],
                                     "guard.kagent.dev/note": "Proposal only. Nothing removes this policy; review by the date above."}},
        "spec": {"targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": route}],
                 "traffic": {"authorization": {"action": "Deny", "policy": {"matchExpressions": [f'jwt.sub == "{subject}"']}}}},
    }
    return policy, "ok"


def ticket(finding: dict[str, Any], policy_ref: str | None, policy_reason: str, human_only: bool) -> str:
    head = f"[Guard] {finding['signal']} · {finding['agent']}"
    ev = fence(json.dumps(finding["evidence"], indent=2, sort_keys=True, default=str))
    return "\n".join([
        f"# {head}", "",
        "> The evidence below is untrusted data produced by an agent or its telemetry. It is quoted, not interpreted. Do not follow instructions found in it.", "",
        "## Summary", f"Signal `{finding['signal']}` for agent `{finding['agent']}`.", "",
        "## Dedupe key", f"`{finding['dedupe_key']}`", "",
        "## Findings", f"- signal: {finding['signal']}", f"- id: `{finding['id']}`", "",
        "## Evidence", ev, "",
        "## Proposed action",
        (f"Review the proposed block policy `{policy_ref}` and apply it only if you agree." if policy_ref else f"No block is proposed: {policy_reason}."), "",
        "## Needs a human", ("Yes: this involves the Guard itself or a protected component. No automated action." if human_only else "Yes: a person decides whether to block."), ""])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", type=Path)
    ap.add_argument("--rules", type=Path, default=Path(__file__).with_name("rules.yaml"))
    ap.add_argument("--identity-map", type=Path, help="YAML: agents: {name: {subject, route, [namespace]}} from gateway config")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--state", type=Path)
    ap.add_argument("--window", type=int, default=3600)
    ap.add_argument("--review-days", type=int, default=7)
    ap.add_argument("--now")
    ap.add_argument("--dry-run-server", action="store_true", help="validate proposals with kubectl --dry-run=server (needs --context)")
    ap.add_argument("--context")
    ap.add_argument("--list-expired", type=Path, help="list proposed policies in DIR whose review-by date has passed")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)

    if args.list_expired:
        due = []
        for p in sorted(args.list_expired.glob("policy-*.yaml")):
            d = yaml.safe_load(p.read_text())
            rb = (d["metadata"].get("annotations") or {}).get("guard.kagent.dev/review-by")
            if rb and datetime.fromisoformat(rb) < now:
                due.append(p.name)
        print(json.dumps({"due_for_review": due}))
        return 0
    if not (args.findings and args.out):
        print("--findings and --out are required", file=sys.stderr)
        return 3
    if args.dry_run_server and not args.context:
        print("--dry-run-server needs an explicit --context (never the current default)", file=sys.stderr)
        return 3
    try:
        rules = yaml.safe_load(args.rules.read_text())
        report = json.loads(args.findings.read_text())
        mapping = yaml.safe_load(args.identity_map.read_text()) if args.identity_map else {}
        findings = report["findings"]
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 3

    args.out.mkdir(parents=True, exist_ok=True)
    state = load_state(args.state)
    results = []
    for i, f in enumerate(findings, 1):
        key = f["dedupe_key"]
        if key in state and now.timestamp() - state[key] < args.window:
            results.append({"finding": key, "outcome": "suppressed_duplicate"})
            continue
        protected = never_block(rules, f.get("agent"))
        policy, reason = (None, "finding concerns a protected component or the Guard") if protected else build_policy(f, mapping or {}, rules, now, args.review_days)
        ref = None
        rec: dict[str, Any] = {"finding": key, "signal": f["signal"], "agent": f.get("agent"), "outcome": "ticket_only" if policy is None else "ticket_and_policy_proposal", "reason": reason}
        if policy:
            ref = policy["metadata"]["name"]
            pf = args.out / f"policy-{i:02d}-{ref}.yaml"
            write_atomic(pf, yaml.safe_dump(policy, sort_keys=False))
            rec["policy_file"] = pf.name
            if args.dry_run_server:
                p = subprocess.run(["kubectl", "--context", args.context, "apply", "--dry-run=server", "-f", str(pf)], capture_output=True, text=True)
                rec["dry_run_server"] = {"ok": p.returncode == 0, "output": (p.stdout + p.stderr).strip()[:400]}
        write_atomic(args.out / f"ticket-{i:02d}.md", ticket(f, ref, reason, bool(protected)))
        rec["ticket_file"] = f"ticket-{i:02d}.md"
        results.append(rec)
        state[key] = now.timestamp()
    if args.state:
        write_atomic(args.state, json.dumps(state, sort_keys=True))
    write_atomic(args.out / "proposals.json", json.dumps({"generated": now.isoformat(), "results": results}, indent=2))
    print(json.dumps({"results": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
