#!/usr/bin/env python3
"""Guard detector: finds rogue agent behaviour in telemetry, deterministically.

Reads normalised events from any of: a2a_capture `*.run.json`, raw A2A task receipts (0.7 or 1.x), OTLP-JSON trace
exports (Tempo `/api/traces`), warden.jsonl, and generic JSONL access logs. Applies the budgets in rules.yaml and prints
findings JSON. It never changes anything.

Signals: oversized_tool_output, long_running, token_burn, forbidden_tool, http_errors, task_failed, warden_block.
Missing data is never clean: an event with no token or tool data, an agent with no telemetry, or an agent with no
tool allowlist is reported under `coverage`, and the status becomes `degraded` rather than `clean`.

Exit: 0 clean | 1 findings | 2 degraded (coverage gaps, no findings) | 3 input error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a2a_shapes import summarize  # noqa: E402

SIGNALS = ("oversized_tool_output", "long_running", "token_burn", "forbidden_tool", "http_errors", "task_failed", "warden_block")


def parse_ts(v: Any) -> datetime | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return datetime.fromtimestamp(v, tz=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def event(**kw: Any) -> dict[str, Any]:
    base = {"src": None, "id": None, "agent": None, "caller": None, "ts": None, "duration_s": None, "tokens": None,
            "tools": None, "status": None, "failed": False, "error_code": None, "warden": None, "max_tool_output": None}
    base.update(kw)
    return base


def _attr(attrs: list[dict[str, Any]], *keys: str) -> Any:
    for a in attrs or []:
        if a.get("key") in keys:
            v = a.get("value") or {}
            for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if k in v:
                    return v[k]
    return None


def _num(v: Any) -> int | None:
    try:
        n = int(v)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def from_otlp(doc: dict[str, Any], path: str) -> list[dict[str, Any]]:
    traces: dict[str, dict[str, Any]] = {}
    for rs in doc.get("resourceSpans") or doc.get("batches") or []:
        res = (rs.get("resource") or {}).get("attributes") or []
        agent = _attr(res, "kagent.agent.name", "gen_ai.agent.name", "service.name")
        for ss in rs.get("scopeSpans") or rs.get("instrumentationLibrarySpans") or []:
            for sp in ss.get("spans") or []:
                tid = sp.get("traceId") or f"{path}:{sp.get('spanId')}"
                t = traces.setdefault(tid, {"agent": agent, "start": None, "end": None, "tokens": None, "tools": [], "tools_seen": False,
                                            "status": None, "caller": None, "spans": set()})
                if sp.get("spanId") in t["spans"]:
                    continue  # duplicate span in the export must not double count
                t["spans"].add(sp.get("spanId"))
                t["agent"] = t["agent"] or agent
                a = sp.get("attributes") or []
                s, e = _num(sp.get("startTimeUnixNano")), _num(sp.get("endTimeUnixNano"))
                if s is not None:
                    t["start"] = s if t["start"] is None else min(t["start"], s)
                if e is not None:
                    t["end"] = e if t["end"] is None else max(t["end"], e)
                ti, to = _num(_attr(a, "gen_ai.usage.input_tokens")), _num(_attr(a, "gen_ai.usage.output_tokens"))
                if ti is not None or to is not None:
                    t["tokens"] = (t["tokens"] or 0) + (ti or 0) + (to or 0)
                name = _attr(a, "gen_ai.tool.name", "mcp.tool.name")
                sname = str(sp.get("name") or "")
                if name is None and sname.startswith("tools/call "):
                    name = sname[len("tools/call "):]
                if name is not None:
                    t["tools"].append(str(name)); t["tools_seen"] = True
                st = _num(_attr(a, "http.response.status_code", "http.status_code"))
                if st is not None and (t["status"] is None or st >= 400 or t["status"] < 400):
                    t["status"] = st if (t["status"] is None or st >= 400) else t["status"]
                t["caller"] = t["caller"] or _attr(a, "enduser.id", "caller")
    out = []
    for tid, t in traces.items():
        dur = (t["end"] - t["start"]) / 1e9 if t["start"] is not None and t["end"] is not None and t["end"] >= t["start"] else None
        out.append(event(src="otlp", id=tid, agent=t["agent"], caller=t["caller"], ts=parse_ts((t["end"] or 0) / 1e9) if t["end"] else None,
                         duration_s=dur, tokens=t["tokens"], tools=t["tools"] if t["tools_seen"] else None, status=t["status"]))
    return out


def load_events(path: Path, agent_hint: str | None) -> list[dict[str, Any]]:
    text = path.read_text()
    if path.suffix == ".jsonl":
        out = []
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except ValueError:
                raise ValueError(f"{path}:{i}: not JSON")
            if not isinstance(d, dict):
                raise ValueError(f"{path}:{i}: not an object")
            if "route" in d and "verdict" in d:
                out.append(event(src="warden", id=f"{path.name}:{i}", agent=d.get("agent"), ts=parse_ts(d.get("ts")), warden=d,
                                 tokens=d.get("tokens_total"), duration_s=d.get("duration_s")))
            else:
                out.append(event(src="log", id=str(d.get("id") or f"{path.name}:{i}"), agent=d.get("agent"), caller=d.get("caller"),
                                 ts=parse_ts(d.get("ts")), duration_s=d.get("duration_s") if d.get("duration_s") is not None else (d["duration_ms"] / 1000 if isinstance(d.get("duration_ms"), (int, float)) else None),
                                 status=_num(d.get("status")), tokens=_num(d.get("tokens")), tools=d.get("tools") if isinstance(d.get("tools"), list) else None))
        return out
    try:
        doc = json.loads(text)
    except ValueError:
        raise ValueError(f"{path}: not JSON")
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: not an object")
    if "resourceSpans" in doc or "batches" in doc:
        return from_otlp(doc, path.name)
    if "run_id" in doc and "case_id" in doc:  # a2a_capture run record
        toks = [doc.get("input_tokens"), doc.get("output_tokens")]
        return [event(src="run", id=doc["run_id"], agent=doc.get("agent"), duration_s=(doc["latency_ms"] / 1000 if isinstance(doc.get("latency_ms"), (int, float)) else None),
                      tokens=(sum(t for t in toks if isinstance(t, int)) if any(isinstance(t, int) for t in toks) else None),
                      tools=[c.get("name") for c in doc.get("tool_calls", [])], failed=doc.get("outcome") != "completed",
                      error_code=(doc.get("outcome_reason") or None) if doc.get("outcome") != "completed" else None)]
    if "jsonrpc" in doc:  # raw A2A receipt
        if "result" not in doc:
            return [event(src="receipt", id=str(doc.get("id")), agent=agent_hint, failed=True, error_code="jsonrpc_error")]
        f = summarize(doc)
        return [event(src="receipt", id=str(doc.get("id")), agent=agent_hint, ts=parse_ts(f["finished"]), duration_s=f["duration_s"], tokens=f["tokens_total"],
                      tools=[c["name"] for c in f["tool_calls"]], failed=not f["completed"], error_code=f["error_code"],
                      max_tool_output=f["max_tool_output_chars"])]
    raise ValueError(f"{path}: unrecognised telemetry shape")


def merged(rules: dict[str, Any], agent: str | None) -> dict[str, Any]:
    r = dict(rules.get("defaults") or {})
    r.update((rules.get("agents") or {}).get(agent or "", {}) or {})
    return r


def evaluate(events: list[dict[str, Any]], rules: dict[str, Any], now: datetime, inventory: list[dict[str, Any]] | None = None,
             contract_tools: dict[str, set[str]] | None = None, window_s: int = 3600) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    bucket = int(now.timestamp() // window_s)

    def add(signal: str, agent: str | None, ev_id: Any, caller: Any, evidence: dict[str, Any]) -> None:
        key = f"{agent}|{signal}|{bucket}"
        findings.append({"signal": signal, "agent": agent, "caller": caller, "id": ev_id, "dedupe_key": key,
                         "id_hash": hashlib.sha256(f"{key}|{ev_id}".encode()).hexdigest()[:12], "evidence": evidence})

    def gap(kind: str, agent: str | None, detail: str) -> None:
        item = {"gap": kind, "agent": agent, "detail": detail}
        if item not in coverage:
            coverage.append(item)

    known = set((rules.get("agents") or {}).keys())
    seen_agents: set[str] = set()
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        if not e["agent"]:
            gap("unattributed_event", None, f"{e['src']} event {e['id']} names no agent")
            continue
        seen_agents.add(e["agent"])
        by_agent.setdefault(e["agent"], []).append(e)
        if e["agent"] not in known:
            gap("unknown_agent", e["agent"], "no per-agent rules; defaults applied")

    for agent, evs in by_agent.items():
        r = merged(rules, agent)
        allowed = set(r.get("allowedTools") or []) | set((contract_tools or {}).get(agent, set()))
        non2xx: dict[str, list[Any]] = {}
        known_status = 0
        hour_tokens, hour_unknown_ts = 0, False
        for e in evs:
            if e["src"] == "warden":
                w = e["warden"] or {}
                if w.get("verdict") != "PASS":
                    add("warden_block", agent, e["id"], None, {"verdict": w.get("verdict"), "route": w.get("route"), "failures": w.get("failures", [])[:5]})
                continue
            if e["failed"]:
                add("task_failed", agent, e["id"], e["caller"], {"error_code": e["error_code"]})
            if e["duration_s"] is not None and e["duration_s"] > r["maxDurationS"]:
                add("long_running", agent, e["id"], e["caller"], {"duration_s": e["duration_s"], "max": r["maxDurationS"]})
            if e["max_tool_output"] is not None and e["max_tool_output"] > r.get("maxToolOutputChars", 200000):
                add("oversized_tool_output", agent, e["id"], e["caller"], {"largest_tool_output_chars": e["max_tool_output"], "max": r.get("maxToolOutputChars", 200000),
                                                                          "why": "a tool result this large cannot fit a model context; the next model call is likely to fail"})
            if e["tokens"] is None:
                if r.get("requireTokens"):
                    gap("no_token_data", agent, f"{e['src']} event {e['id']} has no token usage; cannot judge token burn")
            else:
                if e["tokens"] > r["maxTokensPerRun"]:
                    add("token_burn", agent, e["id"], e["caller"], {"tokens": e["tokens"], "max_per_run": r["maxTokensPerRun"]})
                if e["ts"] is None:
                    hour_unknown_ts = True
                elif 0 <= (now - e["ts"]).total_seconds() <= 3600:
                    hour_tokens += e["tokens"]
            if e["tools"] is None:
                if r.get("requireTools") and allowed:
                    gap("no_tool_data", agent, f"{e['src']} event {e['id']} has no tool data; cannot check the allowlist")
            elif allowed:
                bad = sorted({t for t in e["tools"] if t not in allowed})
                if bad:
                    add("forbidden_tool", agent, e["id"], e["caller"], {"tools": bad, "allowed_count": len(allowed)})
            elif e["tools"]:
                gap("no_allowlist", agent, "agent has no tool allowlist (rules.yaml or a contract); tool use not checked")
            if e["status"] is not None:
                known_status += 1
                if not 200 <= e["status"] < 300:
                    non2xx.setdefault(str(e["caller"] or "unknown"), []).append(e["status"])
        if r.get("maxTokensPerHour") and hour_tokens > r["maxTokensPerHour"]:
            add("token_burn", agent, f"hour:{bucket}", None, {"tokens_last_hour": hour_tokens, "max_per_hour": r["maxTokensPerHour"]})
        if r.get("maxTokensPerHour") and hour_unknown_ts:
            gap("no_timestamp", agent, "some events have no timestamp; the per-hour token budget is under-counted")
        total_bad = sum(len(v) for v in non2xx.values())
        if known_status >= r.get("minEvents", 1) and known_status and total_bad / known_status > r.get("maxNon2xxRatio", 1):
            add("http_errors", agent, f"ratio:{bucket}", None, {"non2xx": total_bad, "of": known_status, "max_ratio": r["maxNon2xxRatio"]})
        for caller, codes in non2xx.items():
            if len(codes) >= r.get("maxNon2xxBurst", 10**9):
                add("http_errors", agent, f"burst:{caller}:{bucket}", caller, {"non2xx_from_caller": len(codes), "codes": sorted(set(codes)), "max_burst": r["maxNon2xxBurst"]})

    # A run that never finished cannot show up as a completed span or receipt: check an independent start inventory.
    finished_ids = {e["id"] for e in events}
    if inventory is None:
        gap("no_inventory", None, "no start inventory supplied: a run that never finished cannot be seen, so a hung agent would read as clean")
    for item in inventory or []:
        started = parse_ts(item.get("started"))
        agent = item.get("agent")
        if started is None or not agent:
            gap("bad_inventory_entry", agent, f"inventory entry {item.get('id')} has no agent or start time")
            continue
        if item.get("id") in finished_ids:
            continue
        age = (now - started).total_seconds()
        if age > merged(rules, agent)["maxDurationS"]:
            add("long_running", agent, item.get("id"), item.get("caller"), {"open_for_s": round(age), "max": merged(rules, agent)["maxDurationS"], "finished": False})
        seen_agents.add(agent)

    for agent, r in (rules.get("agents") or {}).items():
        if r.get("expectRuns") and agent not in seen_agents:
            gap("no_telemetry", agent, "no events at all for an agent that is expected to run: the export may be down")

    src_by_id = {str(e["id"]): e["src"] for e in events}  # lets enforce.py refuse trace-sourced findings: a trace can mix agents
    for f in findings:
        f["source"] = src_by_id.get(str(f["id"]), "aggregate")
    status = "findings" if findings else ("degraded" if coverage else "clean")
    return {"status": status, "now": now.isoformat(), "window_s": window_s, "findings": findings, "coverage": coverage}


def contract_allowlists(directory: Path | None) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    if directory:
        for p in sorted(directory.glob("*.yaml")):
            c = yaml.safe_load(p.read_text())
            tools = set(c.get("allowedTools") or [])
            if tools or c.get("evaluator"):  # the contract's own evaluator is part of the agent's permitted behaviour
                ev = c["evaluator"]
                tools |= {"transfer_to_agent", f"{ev.get('namespace', 'kagent')}__NS__{ev['agent'].replace('-', '_')}"}
            out[c["agent"]] = tools
            out[c["agent"].removesuffix("-agent")] = tools
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=Path, nargs="+", required=True)
    ap.add_argument("--rules", type=Path, default=Path(__file__).with_name("rules.yaml"))
    ap.add_argument("--agent", help="agent name for raw A2A receipts, which do not name their agent")
    ap.add_argument("--inventory", type=Path, help="JSON list of started tasks: id, agent, started, [caller]")
    ap.add_argument("--contracts-dir", type=Path, help="completion contracts: each agent's allowedTools joins its allowlist")
    ap.add_argument("--now", help="ISO time (default: now); for reproducible runs")
    ap.add_argument("--window", type=int, default=3600)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try:
        rules = yaml.safe_load(args.rules.read_text())
        if not isinstance(rules, dict) or "defaults" not in rules:
            raise ValueError(f"{args.rules}: rules need a `defaults` block")
        events = [e for p in args.events for e in load_events(p, args.agent)]
        inventory = json.loads(args.inventory.read_text()) if args.inventory else None
        if inventory is not None and not isinstance(inventory, list):
            raise ValueError("inventory must be a JSON list")
        now = parse_ts(args.now) if args.now else datetime.now(timezone.utc)
        if now is None:
            raise ValueError("--now is not an ISO time")
        report = evaluate(events, rules, now, inventory, contract_allowlists(args.contracts_dir), args.window)
    except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 3
    text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)
    return {"clean": 0, "findings": 1, "degraded": 2}[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
