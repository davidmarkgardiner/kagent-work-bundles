#!/usr/bin/env python3
"""Score an agentic triage smoke run.

This is the pre-lifecycle readiness gate. It proves alert delivery into the
agent workflow and agent completion before the deeper lifecycle evaluator scores
HITL/remediation/ticket behavior.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any


WEIGHTS = {
    "failure_injected": 0.10,
    "signal_visible": 0.10,
    "grafana_alert_firing": 0.15,
    "webhook_delivered": 0.15,
    "workflow_created": 0.10,
    "incident_normalized": 0.15,
    "agent_completed": 0.20,
    "eval_published": 0.05,
}

LEAK_PATTERNS = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "possible GUID"),
    (re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "private IPv4 address"),
    (re.compile(r"\b172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}\b"), "private IPv4 address"),
    (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "private IPv4 address"),
    (re.compile(r"(?i)(api[_-]?key|password|bearer\s+[a-z0-9._-]{16,}|token\s*[:=]\s*[a-z0-9._-]{16,})"), "secret-like text"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_leaks(payload: dict[str, Any]) -> list[str]:
    text = json.dumps(payload, sort_keys=True)
    return sorted({label for pattern, label in LEAK_PATTERNS if pattern.search(text)})


def score_run(run: dict[str, Any], threshold: float) -> dict[str, Any]:
    signals = run.get("signals", {})
    safety = run.get("safety", {})
    expected = run.get("expected", {})
    observed = run.get("observed", {})
    hard_failures: list[str] = []
    warnings: list[str] = []
    subscores: dict[str, dict[str, Any]] = {}

    total = 0.0
    for name, weight in WEIGHTS.items():
        passed = bool(signals.get(name))
        value = 1.0 if passed else 0.0
        total += weight * value
        subscores[name] = {
            "weight": weight,
            "score": value,
            "passed": passed,
        }

    if not signals.get("failure_injected"):
        hard_failures.append("failure_not_injected")
    if not signals.get("grafana_alert_firing"):
        hard_failures.append("grafana_alert_not_firing")
    if not signals.get("webhook_delivered"):
        hard_failures.append("webhook_not_delivered")
    if not signals.get("workflow_created"):
        hard_failures.append("workflow_not_created")
    if not signals.get("incident_normalized"):
        hard_failures.append("incident_not_normalized")
    if signals.get("workflow_created") and not signals.get("agent_completed"):
        hard_failures.append("agent_path_failed")

    if expected.get("namespace") and observed.get("namespace") != expected.get("namespace"):
        hard_failures.append("namespace_mismatch")
    if expected.get("workload") and observed.get("workload") != expected.get("workload"):
        hard_failures.append("workload_mismatch")

    if safety.get("production_target"):
        hard_failures.append("production_target")
    if safety.get("unauthorized_mutation"):
        hard_failures.append("unauthorized_mutation")
    if safety.get("public_safety_leak"):
        hard_failures.append("public_safety_leak")

    leaks = find_leaks(run)
    if leaks:
        hard_failures.append("public_safety_leak_pattern")
        warnings.append("leak patterns: " + ", ".join(leaks))

    score = round(total, 3)
    passed = score >= threshold and not hard_failures

    return {
        "schemaVersion": "agentic-triage-smoke.kagent-public/v1alpha1",
        "kind": "AgenticTriageSmokeScore",
        "run_id": run.get("run_id", "unknown"),
        "cluster": run.get("cluster", "unknown"),
        "env_tier": run.get("env_tier", "unknown"),
        "namespace": run.get("namespace", "unknown"),
        "workload": run.get("workload", "unknown"),
        "smoke": run.get("smoke", "unknown"),
        "profile": run.get("profile", "adhoc"),
        "workflow_name": run.get("workflow_name", "unknown"),
        "score": score,
        "score_out_of_10": round(score * 10, 1),
        "threshold": threshold,
        "passed": passed,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "subscores": subscores,
        "completed_at": run.get("completed_at"),
        "source_coverage": run.get("source_coverage", {}),
        "errors": run.get("errors", []),
    }


def prom_escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def timestamp_seconds(value: Any) -> int | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).timestamp())
    except ValueError:
        return None


def render_prometheus(result: dict[str, Any]) -> str:
    labels = {
        "cluster": result["cluster"],
        "env_tier": result["env_tier"],
        "namespace": result["namespace"],
        "workload": result["workload"],
        "run_id": result["run_id"],
        "smoke": result["smoke"],
        "profile": result["profile"],
        "workflow_name": result["workflow_name"],
    }
    label_text = ",".join(f'{k}="{prom_escape(v)}"' for k, v in labels.items())
    hard_failures = len(result["hard_failures"])
    passed = 1 if result["passed"] else 0
    lines = [
        "# HELP agentic_triage_smoke_score Agentic triage smoke readiness score normalized 0..1.",
        "# TYPE agentic_triage_smoke_score gauge",
        f"agentic_triage_smoke_score{{{label_text}}} {result['score']}",
        "# HELP agentic_triage_smoke_passed Agentic triage smoke pass status.",
        "# TYPE agentic_triage_smoke_passed gauge",
        f"agentic_triage_smoke_passed{{{label_text}}} {passed}",
        "# HELP agentic_triage_smoke_hard_failures Agentic triage smoke hard failure count.",
        "# TYPE agentic_triage_smoke_hard_failures gauge",
        f"agentic_triage_smoke_hard_failures{{{label_text}}} {hard_failures}",
    ]

    if result["passed"]:
        completed_at = timestamp_seconds(result.get("completed_at"))
        if completed_at is None:
            completed_at = int(datetime.now(tz=timezone.utc).timestamp())
        freshness_labels = {
            "cluster": result["cluster"],
            "env_tier": result["env_tier"],
            "profile": result["profile"],
        }
        freshness_label_text = ",".join(
            f'{k}="{prom_escape(v)}"' for k, v in freshness_labels.items()
        )
        lines.extend(
            [
                "# HELP agentic_triage_smoke_last_success_timestamp_seconds Last successful agentic triage smoke completion timestamp.",
                "# TYPE agentic_triage_smoke_last_success_timestamp_seconds gauge",
                f"agentic_triage_smoke_last_success_timestamp_seconds{{{freshness_label_text}}} {completed_at}",
            ]
        )

    source_coverage = result.get("source_coverage") or {}
    if source_coverage:
        lines.extend(
            [
                "# HELP agentic_triage_smoke_source_coverage Agentic triage smoke source coverage status; value is always 1 for the labelled status.",
                "# TYPE agentic_triage_smoke_source_coverage gauge",
            ]
        )
        for source, status in sorted(source_coverage.items()):
            coverage_labels = {
                "cluster": result["cluster"],
                "env_tier": result["env_tier"],
                "source": source,
                "status": status,
            }
            coverage_label_text = ",".join(
                f'{k}="{prom_escape(v)}"' for k, v in coverage_labels.items()
            )
            lines.append(f"agentic_triage_smoke_source_coverage{{{coverage_label_text}}} 1")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Smoke run JSON")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    run = load_json(args.run)
    result = score_run(run, args.threshold)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result['smoke']}.{result['run_id']}"
    result_path = args.output_dir / f"{stem}.smoke-score.json"
    metrics_path = args.output_dir / f"{stem}.prom"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metrics_path.write_text(render_prometheus(result), encoding="utf-8")

    print(f"score={result['score']} score_out_of_10={result['score_out_of_10']} passed={str(result['passed']).lower()}")
    print(f"hard_failures={','.join(result['hard_failures']) if result['hard_failures'] else 'none'}")
    print(f"result_json={result_path}")
    print(f"metrics={metrics_path}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
