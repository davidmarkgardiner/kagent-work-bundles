#!/usr/bin/env python3
"""Emit a sanitized review-manager routing payload for lifecycle eval results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from reporting import utc_now_iso, write_json


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def result_files(results_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in results_dir.glob("*.json")
        if path.name != "lifecycle-run.json"
    )


def latest_result(results_dir: Path) -> dict[str, Any]:
    candidates = result_files(results_dir)
    if not candidates:
        raise SystemExit(f"no lifecycle eval result JSON found in {results_dir}")
    return load_json(candidates[-1])


def build_route(result: dict[str, Any]) -> dict[str, Any]:
    passed = bool(result.get("passed"))
    return {
        "schemaVersion": "agent-evals.kagent-public/v1alpha1",
        "kind": "LifecycleEvalReviewRoute",
        "created_at": utc_now_iso(),
        "route_required": not passed,
        "review_manager_route": "none" if passed else "review-manager",
        "next_action": "ticket may proceed to close" if passed else "keep ticket open and attach sanitized eval summary",
        "run_id": result.get("run_id", "{{RUN_ID}}"),
        "case_id": result.get("case_id", "{{CASE_ID}}"),
        "incident_id": result.get("incident_id", "{{INCIDENT_ID}}"),
        "workflow_name": result.get("workflow_name", "{{WORKFLOW_NAME}}"),
        "score": result.get("score"),
        "min_score": result.get("min_score"),
        "passed": passed,
        "hard_failures": result.get("hard_failures", []),
        "warnings": result.get("warnings", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    route = build_route(latest_result(args.results_dir))
    write_json(args.output, route)
    if route["route_required"]:
        print(f"REVIEW_MANAGER_ROUTE: created {args.output}")
    else:
        print("REVIEW_MANAGER_ROUTE: not_required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
