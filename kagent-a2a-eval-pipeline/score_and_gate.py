#!/usr/bin/env python3
"""Score captured A2A runs with the existing deterministic scorer, apply the
gate-level checks it does not cover, and decide the pipeline verdict.

Uses the scorer vendored at scorer/score-agent-run.py (a verbatim copy of observability/agent-evals/scripts/score-agent-run.py), so the bundle works on its own.

Per case, with k repeats (pass^k):
  pass     every repeat exists, completed, and passed scorer + gate checks
  fail     at least one repeat completed and failed
  error    no quality failure, but a repeat is agent_error / infra_error
  missing  fewer run files than expected repeats

Exit codes: 0 all pass | 1 any fail | 3 errors or missing, no fail | 2 nothing to score.
Errors and missing runs stay in the denominator; they are never a pass.

Gate-level checks (in addition to the scorer's own hard failures):
  hardFailOnMissingTool  (default true)  a required tool was never called
  maxToolCalls           (optional)      more tool calls than budgeted
  failOnToolError        (default false) a tool call returned an error
  completion contract    (--contracts-dir) the agent closed the runtime loop: called its
                         evaluator agent over A2A and got a bound PASS (verify_completion.py)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr

HERE = Path(__file__).resolve().parent
DEFAULT_SCORER = HERE / "scorer" / "score-agent-run.py"


def load_scorer(path: Path):
    sys.path.insert(0, str(path.resolve().parent))  # scorer imports sibling reporting.py
    spec =importlib.util.spec_from_file_location("score_agent_run", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load scorer at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["score_agent_run"] = module
    spec.loader.exec_module(module)
    return module


def load_completion(contracts_dir: Path | None):
    """Return (verify_completion module, {agent: contract}) or (None, {})."""
    if contracts_dir is None:
        return None, {}
    spec = importlib.util.spec_from_file_location("verify_completion", HERE / "verify_completion.py")
    vc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vc)
    contracts = {}
    for path in sorted(contracts_dir.glob("*.yaml")):
        c = vc.load_contract(path)
        if c["agent"] in contracts:
            raise SystemExit(f"two completion contracts for agent {c['agent']}")
        contracts[c["agent"]] = c
    return vc, contracts


def completion_checks(vc, contracts, require: bool, run: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any] | None]:
    """Return (hard failures, warnings, verdict)."""
    if vc is None:
        return [], [], None
    contract = contracts.get(run["agent"])
    if contract is None:
        msg = f"no completion contract for agent {run['agent']}"
        return ([msg], [], None) if require else ([], [msg + "; runtime A2A loop not checked"], None)
    receipt_path = Path(run["_capture_dir"]) / "receipts" / f"{run['case_id']}.r{run.get('repeat')}.json"
    if not receipt_path.exists():
        return [f"completion gate: receipt missing ({receipt_path.name})"], [], None
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("id") != run.get("run_id"):  # JSON-RPC id is the run id a2a_capture sent
        return [f"completion gate: receipt {receipt_path.name} does not belong to run {run.get('run_id')}"], [], None
    verdict = vc.verify(contract, receipt)
    if verdict["verdict"] == "PASS":
        return [], [f"completion gate: {w}" for w in verdict.get("warnings", [])], verdict
    return [f"completion gate {verdict['verdict']}: {f}" for f in verdict["failures"]] or \
        [f"completion gate {verdict['verdict']}"], [], verdict


def gate_checks(case: dict[str, Any], run: dict[str, Any]) -> tuple[list[str], list[str]]:
    expected = case["spec"]["expected"]
    scoring = case["spec"].get("scoring", {})
    called = [c.get("name") for c in run.get("tool_calls", [])]
    hard, notes = [], []

    missing = [t for t in expected.get("requiredTools", []) if t not in called]
    if missing and scoring.get("hardFailOnMissingTool", True):
        hard.append(f"required tool never called: {', '.join(missing)}")
    budget = scoring.get("maxToolCalls")
    if budget is not None and len(called) > budget:
        hard.append(f"tool call budget exceeded: {len(called)} > {budget}")
    if run.get("tool_errors"):
        msg = f"tool calls returned errors: {', '.join(run['tool_errors'])}"
        (hard if scoring.get("failOnToolError", False) else notes).append(msg)
    if expected.get("forbiddenTools") and run.get("trajectory_source") == "a2a_history":
        notes.append("forbidden-tool check uses A2A history only; join gateway/OTel audit for proof")
    return hard, notes


def errored_result(case: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "AgentEvalResult", "run_id": run["run_id"], "case_id": run["case_id"], "agent": run["agent"],
        "repeat": run.get("repeat"), "status": run["outcome"], "passed": False, "score": None,
        "min_score": case["spec"].get("scoring", {}).get("minScore"),
        "hard_failures": [], "warnings": [run.get("outcome_reason", "")], "trace_id": run.get("trace_id"),
        "latency_ms": run.get("latency_ms"),
    }


def junit(results: list[dict[str, Any]]) -> str:
    fails = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] not in {"pass", "fail"})
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<testsuite name="kagent-agent-evals" tests="{len(results)}" failures="{fails}" errors="{errors}">']
    for r in results:
        secs = (r.get("latency_ms") or 0) / 1000
        name = f"{r['case_id']} [r{r.get('repeat')}]"
        lines.append(f'  <testcase classname={quoteattr(r["agent"])} name={quoteattr(name)} time="{secs:.1f}">')
        detail = escape("\n".join(r.get("hard_failures", []) + r.get("warnings", [])))
        if r["status"] == "fail":
            msg = (r.get("hard_failures") or [f"score {r.get('score')} < {r.get('min_score')}"])[0]
            lines.append(f'    <failure message={quoteattr(msg)}>{detail}</failure>')
        elif r["status"] != "pass":
            lines.append(f'    <error message={quoteattr(r["status"])}>{detail}</error>')
        lines.append(f'    <system-out>trace_id={escape(str(r.get("trace_id")))} score={r.get("score")}</system-out>')
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dirs", type=Path, nargs="+", required=True,
                    help="one or more a2a_capture.py --out dirs (one per matrix shard)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repeat", type=int, required=True, help="repeats each case was captured with")
    ap.add_argument("--scorer", type=Path, default=DEFAULT_SCORER)
    ap.add_argument("--contracts-dir", type=Path,
                    help="completion contracts (completion-gate/contracts); enforce the runtime A2A loop")
    ap.add_argument("--require-contracts", action="store_true",
                    help="an agent with no completion contract fails instead of being skipped")
    ap.add_argument("--expect-agents", nargs="*", default=[],
                    help="agents that must appear; one with no captured cases is reported missing")
    args = ap.parse_args()

    scorer = load_scorer(args.scorer)
    vc, contracts = load_completion(args.contracts_dir)
    if args.require_contracts and vc is None:
        raise SystemExit("--require-contracts needs --contracts-dir")
    (args.out / "results").mkdir(parents=True, exist_ok=True)

    cases: dict[str, dict[str, Any]] = {}
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cap in args.capture_dirs:
        # Key by agent/case: a matrix shard per agent reuses the same case names.
        for path in sorted((cap / "rendered-cases").glob("*.yaml")):
            case = scorer.load_yaml(path)
            cases[f"{case['spec']['agent']}/{case['metadata']['name']}"] = case
        for path in sorted((cap / "runs").glob("*.run.json")):
            run = scorer.load_json(path)
            run["_capture_dir"] = str(cap)
            runs[f"{run['agent']}/{run['case_id']}"].append(run)

    if not cases and not args.expect_agents:
        print("no rendered cases found; nothing to score", file=sys.stderr)
        return 2

    all_results: list[dict[str, Any]] = []
    verdicts: dict[str, str] = {}
    for key, case in sorted(cases.items()):
        case_results = []
        repeats = [r.get("repeat") for r in runs.get(key, [])]
        if len(repeats) != len(set(repeats)):
            raise SystemExit(f"duplicate repeat numbers for {key}: {repeats}")
        for run in sorted(runs.get(key, []), key=lambda r: r.get("repeat", 0)):
            if run.get("outcome") != "completed":
                result = errored_result(case, run)
            else:
                result = scorer.score(case, run)
                hard, notes = gate_checks(case, run)
                completion_hard, completion_notes, completion = completion_checks(vc, contracts, args.require_contracts, run)
                hard += completion_hard
                notes += completion_notes
                if completion is not None:
                    result["completion_gate"] = completion
                result["hard_failures"] += hard
                result["warnings"] += notes
                result["passed"] = result["passed"] and not hard
                result["status"] = "pass" if result["passed"] else "fail"
                result.update(repeat=run.get("repeat"), latency_ms=run.get("latency_ms"),
                              trajectory_source=run.get("trajectory_source"),
                              case_sha256=run.get("case_sha256"), commit_sha=run.get("commit_sha"))
            scorer.write_json(args.out / "results" / f"{key.replace('/', '__')}.r{run.get('repeat')}.json", result)
            case_results.append(result)
        all_results += case_results

        statuses = {r["status"] for r in case_results}
        if "fail" in statuses:
            verdicts[key] = "fail"
        elif statuses - {"pass"}:
            verdicts[key] = "error"
        elif len(case_results) < args.repeat:
            verdicts[key] = "missing"
        else:
            verdicts[key] = "pass"

    seen_agents = {key.split("/", 1)[0] for key in cases}
    for agent in args.expect_agents:
        if agent not in seen_agents:
            verdicts[f"{agent}/*"] = "missing"
            runs[f"{agent}/*"] = []

    for key, verdict in verdicts.items():
        if verdict == "missing":
            agent, name = key.split("/", 1)
            all_results.append({"case_id": name, "agent": agent, "repeat": "missing", "status": "missing",
                                "warnings": [f"expected {args.repeat} runs, found {len(runs.get(key, []))}"]})

    (args.out / "junit.xml").write_text(junit(all_results))

    counts = defaultdict(int)
    for v in verdicts.values():
        counts[v] += 1
    rows = ["| Case | Agent | Verdict | Scores (per repeat) | First problem |", "|---|---|---|---|---|"]
    for key, verdict in sorted(verdicts.items()):
        agent, name = key.split("/", 1)
        rs = [r for r in all_results if r["agent"] == agent and r["case_id"] == name]
        scores = ", ".join(str(r.get("score")) for r in rs if r.get("repeat") != "missing") or "-"
        problem = next((p for r in rs for p in r.get("hard_failures", []) + r.get("warnings", []) if p), "")
        rows.append(f"| {name} | {agent} | **{verdict}** | {scores} | {problem[:120].replace('|', '/')} |")
    summary = (f"# kagent agent eval\n\npass^{args.repeat}: {counts['pass']}/{len(verdicts)} cases pass "
               f"(fail {counts['fail']}, error {counts['error']}, missing {counts['missing']})\n\n" + "\n".join(rows) + "\n")
    (args.out / "summary.md").write_text(summary)
    (args.out / "summary.json").write_text(json.dumps({"repeat": args.repeat, "verdicts": verdicts,
                                                       "counts": dict(counts)}, indent=2, sort_keys=True) + "\n")
    print(summary)

    if counts["fail"]:
        return 1
    if counts["error"] or counts["missing"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
