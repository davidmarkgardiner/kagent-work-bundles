#!/usr/bin/env python3
"""Summarize agent and lifecycle eval JSON results and optionally emit Prometheus text metrics."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from metrics import render_prometheus_metrics


def load_results(results_dir: Path) -> list[dict]:
    results = []
    for path in sorted(results_dir.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("kind") in {"AgentEvalResult", "AgentLifecycleEvalResult"}:
            results.append(data)
    return results


def render_markdown(results: list[dict]) -> str:
    lines = [
        "# Kagent Agent Eval Score Summary",
        "",
        "| Agent | Runs | Avg score | Passed | Hard failures |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        if result.get("kind") == "AgentEvalResult":
            by_agent[result["agent"]].append(result)

    for agent, agent_results in sorted(by_agent.items()):
        avg_score = round(mean(float(item["score"]) for item in agent_results), 3)
        passed = sum(1 for item in agent_results if item.get("passed"))
        hard_failures = sum(len(item.get("hard_failures", [])) for item in agent_results)
        lines.append(f"| `{agent}` | {len(agent_results)} | {avg_score} | {passed} | {hard_failures} |")

    lines += ["", "## Agent Runs", "", "| Case | Agent | Score | Passed | Hard failures |", "| --- | --- | ---: | --- | --- |"]
    for result in sorted([item for item in results if item.get("kind") == "AgentEvalResult"], key=lambda item: (item["agent"], item["case_id"], item["run_id"])):
        hard_failures = "; ".join(result.get("hard_failures", [])) or "None"
        lines.append(
            f"| `{result['case_id']}` | `{result['agent']}` | {result['score']} | {str(result['passed']).lower()} | {hard_failures} |"
        )

    lifecycle_results = [item for item in results if item.get("kind") == "AgentLifecycleEvalResult"]
    if lifecycle_results:
        lines += ["", "## Lifecycle Runs", "", "| Case | Run | Incident | Workflow | Score | Passed | Hard failures |", "| --- | --- | --- | --- | ---: | --- | --- |"]
        for result in sorted(lifecycle_results, key=lambda item: (item["case_id"], item["run_id"])):
            hard_failures = "; ".join(result.get("hard_failures", [])) or "None"
            lines.append(
                f"| `{result['case_id']}` | `{result['run_id']}` | `{result.get('incident_id')}` | `{result.get('workflow_name')}` | {result['score']} | {str(result['passed']).lower()} | {hard_failures} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--summary-md", type=Path)
    parser.add_argument("--metrics", type=Path)
    args = parser.parse_args()

    results = load_results(args.results_dir)
    if not results:
        raise SystemExit(f"no AgentEvalResult JSON files found in {args.results_dir}")

    if args.summary_md:
        args.summary_md.parent.mkdir(parents=True, exist_ok=True)
        args.summary_md.write_text(render_markdown(results), encoding="utf-8")
    else:
        print(render_markdown(results))

    if args.metrics:
        args.metrics.parent.mkdir(parents=True, exist_ok=True)
        args.metrics.write_text(render_prometheus_metrics(results), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
