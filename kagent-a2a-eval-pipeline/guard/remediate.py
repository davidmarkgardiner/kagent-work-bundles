#!/usr/bin/env python3
"""Overseer fix-it step: switch a broken agent to an approved fallback ModelConfig, in plain code, with hard limits.

The overseer agent may RECOMMEND a fix; this tool decides and applies it. It acts only on facts it can check itself:
- the agent and both ModelConfigs are named in guard/fallbacks.yaml (an allowlist); anything else is refused;
- a model-route probe (guard/model_probe.py output) of the agent's CURRENT ModelConfig shows a failure kind listed in
  `triggerKinds` (default: rate_limited, server_error, timeout, connect). 401/403, 400/404 and DNS errors go to a person;
- a probe of the FALLBACK ModelConfig shows `ok`; each probe's model must match the ModelConfig it claims to test;
- caps: one switch per agent per cooldown, `maxSwitchesPerHour` overall (counted from the ledger AND the agents' annotations),
  a kill switch (file `guard-remediate.disabled` next to the ledger, or GUARD_REMEDIATE_DISABLED=1), and a never-touch list;
- server dry-run, patch, then read back: the agent must report Ready on the new ModelConfig, or the switch is reverted.
Every decision is one ledger line, and a ticket body is written. `revert` puts the previous ModelConfig back.
Exit: 0 switched / reverted | 1 refused | 3 bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

FROM, AT = "guard.kagent.dev/remediated-from", "guard.kagent.dev/remediated-at"
DEFAULTS = {"triggerKinds": ["rate_limited", "server_error", "timeout", "connect"], "maxSwitchesPerHour": 2,
            "perAgentCooldownS": 3600, "namespace": "kagent", "neverTouch": [], "agents": {}, "readbackTimeoutS": 90}


def kubectl(ctx: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["kubectl", "--context", ctx, *args], capture_output=True, text=True, input=stdin, timeout=120)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ledger(path: Path, rec: dict[str, Any]) -> None:
    with path.open("a") as f:
        f.write(json.dumps({"ts": now_iso(), **rec}) + "\n")


def model_config_of(agent: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Return (current ModelConfig name, merge patch builder key) for kagent 1.x (v1alpha3) or 0.7 (v1alpha2) agents."""
    spec = agent.get("spec") or {}
    inline = ((spec.get("template") or {}).get("inline") or {})
    if isinstance(inline.get("modelConfig"), dict):
        return inline["modelConfig"].get("name"), {"spec": {"template": {"inline": {"modelConfig": {"name": None}}}}}
    decl = spec.get("declarative") or {}
    if isinstance(decl.get("modelConfig"), str):
        return decl["modelConfig"], {"spec": {"declarative": {"modelConfig": None}}}
    return None, {}


def patch_for(shape: dict[str, Any], name: str, annotations: dict[str, str | None]) -> dict[str, Any]:
    p = json.loads(json.dumps(shape))
    if "template" in p["spec"]:
        p["spec"]["template"]["inline"]["modelConfig"]["name"] = name
    else:
        p["spec"]["declarative"]["modelConfig"] = name
    p["metadata"] = {"annotations": annotations}
    return p


def ready_on(agent: dict[str, Any], mc: str) -> bool:
    cur, _ = model_config_of(agent)
    conds = {c.get("type"): c for c in (agent.get("status") or {}).get("conditions") or []}
    gen = (agent.get("metadata") or {}).get("generation")
    r = conds.get("Ready") or {}
    return cur == mc and r.get("status") == "True" and (r.get("observedGeneration") in (None, gen))


def switches_last_hour(ledger_path: Path, agents: list[dict[str, Any]], now: float) -> int:
    n = 0
    if ledger_path.exists():
        for line in ledger_path.read_text().splitlines():
            try:
                rec = json.loads(line)
                t = datetime.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            except (ValueError, KeyError):
                continue
            if rec.get("decision") == "switched" and now - t < 3600:
                n += 1
    cluster = 0
    for a in agents:  # a lost ledger must not reset the cap
        at = ((a.get("metadata") or {}).get("annotations") or {}).get(AT)
        try:
            if at and now - datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() < 3600:
                cluster += 1
        except ValueError:
            cluster += 1  # an unreadable timestamp counts against the cap
    return max(n, cluster)


def ticket(agent: str, ns: str, old: str, new: str, probe: dict[str, Any], fb: dict[str, Any], outcome: str) -> str:
    def fence(obj: Any) -> str:
        return "```json\n" + json.dumps(obj, indent=1)[:2000].replace("```", "'''") + "\n```"
    return "\n".join([
        f"# Agent remediated: {agent} switched to a fallback model", "",
        f"**Outcome:** {outcome}", f"**Agent:** `{ns}/{agent}`", f"**ModelConfig:** `{old}` -> `{new}`", "",
        "## Why (checked in code, not by a model)",
        f"The agent's model route failed a one-token probe with `{probe.get('kind')}` (HTTP {probe.get('http')}); the fallback answered `ok`.",
        "", "Probe of the failing route:", fence({k: probe.get(k) for k in ("model", "kind", "http", "retry_after_s", "latency_ms", "detail")}),
        "Probe of the fallback route:", fence({k: fb.get(k) for k in ("model", "kind", "http", "latency_ms")}), "",
        "## What a person should do",
        f"- Fix or wait out the failing route, then put the agent back: `guard/remediate.py revert --agent {agent} ...`.",
        "- Check the fallback is acceptable for this agent's work (it may be a smaller or slower model).", "",
        "## Labels", "agent-health, remediated, needs-review", ""])


def load_cfg(path: Path) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg.update(yaml.safe_load(path.read_text()) or {})
    return cfg


def cmd_apply(a: argparse.Namespace) -> int:
    cfg = load_cfg(a.fallbacks)
    ns, L = cfg["namespace"], a.ledger
    base = {"agent": a.agent, "namespace": ns, "action": "switch"}

    def refuse(reason: str) -> int:
        ledger(L, {**base, "decision": "refused", "reason": reason})
        print(json.dumps({"decision": "refused", "reason": reason}))
        return 1

    if os.environ.get("GUARD_REMEDIATE_DISABLED") == "1" or (L.parent / "guard-remediate.disabled").exists():
        return refuse("kill switch is on")
    if a.agent in cfg["neverTouch"]:
        return refuse("agent is on the never-touch list")
    entry = (cfg["agents"] or {}).get(a.agent)
    if not entry:
        return refuse("agent is not in fallbacks.yaml")
    try:
        probe, fb = json.loads(a.probe.read_text()), json.loads(a.fallback_probe.read_text())
    except (OSError, ValueError) as exc:
        print(json.dumps({"decision": "error", "error": f"probe file: {exc}"}), file=sys.stderr)
        return 3
    if probe.get("kind") not in cfg["triggerKinds"]:
        return refuse(f"current route probe is '{probe.get('kind')}', not a trigger ({', '.join(cfg['triggerKinds'])}); a person handles it")
    if fb.get("kind") != "ok":
        return refuse(f"fallback probe is '{fb.get('kind')}', not ok")
    g = kubectl(a.context, "-n", ns, "get", "agent", a.agent, "-o", "json")
    if g.returncode != 0:
        return refuse(f"cannot read agent: {g.stderr.strip()[:200]}")
    agent = json.loads(g.stdout)
    cur, shape = model_config_of(agent)
    if not cur:
        return refuse("cannot find the agent's ModelConfig field")
    allowed = [entry["primary"], *entry.get("fallbacks", [])]
    if cur not in allowed:
        return refuse(f"current ModelConfig '{cur}' is not listed for this agent")
    target = next((m for m in entry.get("fallbacks", []) if m != cur), None)
    if a.to:
        if a.to not in entry.get("fallbacks", []) or a.to == cur:
            return refuse(f"'{a.to}' is not an approved fallback here")
        target = a.to
    if not target:
        return refuse("no other approved fallback")
    for name, pr in ((cur, probe), (target, fb)):  # a probe must test the ModelConfig it claims to
        m = kubectl(a.context, "-n", ns, "get", "modelconfig", name, "-o", "jsonpath={.spec.model}")
        if m.returncode != 0 or m.stdout.strip() != pr.get("model"):
            return refuse(f"probe model '{pr.get('model')}' does not match ModelConfig {name} ('{m.stdout.strip()}')")
    now = time.time()
    ann = (agent.get("metadata") or {}).get("annotations") or {}
    try:
        last = datetime.strptime(ann[AT], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() if AT in ann else 0
    except ValueError:
        last = now
    if now - last < cfg["perAgentCooldownS"]:
        return refuse("agent was switched inside its cooldown; a person decides")
    al = kubectl(a.context, "-n", ns, "get", "agents", "-o", "json")
    peers = json.loads(al.stdout).get("items", []) if al.returncode == 0 else []
    if switches_last_hour(L, peers, now) >= cfg["maxSwitchesPerHour"]:
        return refuse("hourly switch cap reached")
    body = json.dumps(patch_for(shape, target, {FROM: cur, AT: now_iso()}))
    d = kubectl(a.context, "-n", ns, "patch", "agent", a.agent, "--type", "merge", "-p", body, "--dry-run=server")
    if d.returncode != 0:
        return refuse(f"server dry-run refused: {d.stderr.strip()[:200]}")
    p = kubectl(a.context, "-n", ns, "patch", "agent", a.agent, "--type", "merge", "-p", body)
    if p.returncode != 0:
        return refuse(f"patch failed: {p.stderr.strip()[:200]}")
    deadline, ok = time.time() + cfg["readbackTimeoutS"], False
    while time.time() < deadline:
        r = kubectl(a.context, "-n", ns, "get", "agent", a.agent, "-o", "json")
        if r.returncode == 0 and ready_on(json.loads(r.stdout), target):
            ok = True
            break
        time.sleep(3)
    if not ok:  # put it back rather than leave a half-switched agent
        kubectl(a.context, "-n", ns, "patch", "agent", a.agent, "--type", "merge", "-p", json.dumps(patch_for(shape, cur, {FROM: None, AT: now_iso()})))
        ledger(L, {**base, "decision": "reverted_not_ready", "from": cur, "to": target})
        print(json.dumps({"decision": "reverted_not_ready", "from": cur, "to": target}))
        return 1
    ledger(L, {**base, "decision": "switched", "from": cur, "to": target, "trigger": probe.get("kind"), "http": probe.get("http")})
    a.out.mkdir(parents=True, exist_ok=True)
    t = a.out / f"remediation-{a.agent}.md"
    t.write_text(ticket(a.agent, ns, cur, target, probe, fb, "switched and read back: the agent reports Ready on the fallback"))
    print(json.dumps({"decision": "switched", "from": cur, "to": target, "ticket": str(t)}))
    return 0


def cmd_revert(a: argparse.Namespace) -> int:
    cfg = load_cfg(a.fallbacks)
    ns = cfg["namespace"]
    g = kubectl(a.context, "-n", ns, "get", "agent", a.agent, "-o", "json")
    if g.returncode != 0:
        print(json.dumps({"decision": "refused", "reason": g.stderr.strip()[:200]}))
        return 1
    agent = json.loads(g.stdout)
    prev = ((agent.get("metadata") or {}).get("annotations") or {}).get(FROM)
    entry = (cfg["agents"] or {}).get(a.agent) or {}
    if not prev or prev != entry.get("primary"):
        ledger(a.ledger, {"agent": a.agent, "namespace": ns, "action": "revert", "decision": "refused", "reason": "no recorded switch from the primary"})
        print(json.dumps({"decision": "refused", "reason": "no recorded switch from the primary ModelConfig"}))
        return 1
    cur, shape = model_config_of(agent)
    p = kubectl(a.context, "-n", ns, "patch", "agent", a.agent, "--type", "merge", "-p", json.dumps(patch_for(shape, prev, {FROM: None})))
    ok = p.returncode == 0
    ledger(a.ledger, {"agent": a.agent, "namespace": ns, "action": "revert", "decision": "reverted" if ok else "failed", "from": cur, "to": prev})
    print(json.dumps({"decision": "reverted" if ok else "failed", "from": cur, "to": prev}))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("apply", "revert"):
        s = sub.add_parser(name)
        s.add_argument("--agent", required=True)
        s.add_argument("--context", required=True, help="explicit kubectl context; never the current one")
        s.add_argument("--fallbacks", type=Path, required=True)
        s.add_argument("--ledger", type=Path, required=True)
        if name == "apply":
            s.add_argument("--probe", type=Path, required=True, help="model_probe.py output for the agent's current ModelConfig")
            s.add_argument("--fallback-probe", type=Path, required=True, help="model_probe.py output for the fallback")
            s.add_argument("--to", help="a specific approved fallback (default: the first listed that differs)")
            s.add_argument("--out", type=Path, default=Path("out/remediation"))
    a = ap.parse_args()
    try:
        return cmd_apply(a) if a.cmd == "apply" else cmd_revert(a)
    except (subprocess.TimeoutExpired, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"decision": "error", "error": str(exc)[:300]}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
