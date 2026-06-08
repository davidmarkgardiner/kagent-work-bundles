#!/usr/bin/env python3
"""Independent Prometheus metric rendering for kagent eval results."""

from __future__ import annotations

from typing import Any


def prometheus_label_value(value: Any) -> str:
    """Return a Prometheus text-format safe label value."""
    text = str(value)
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def labels(items: dict[str, Any]) -> str:
    return ",".join(f'{key}="{prometheus_label_value(value)}"' for key, value in items.items())


def bool_metric(value: Any) -> int:
    return 1 if bool(value) else 0


def render_agent_eval_metrics(results: list[dict[str, Any]]) -> list[str]:
    lines = []
    for result in [item for item in results if item.get("kind") == "AgentEvalResult"]:
        result_labels = labels({
            "agent": result["agent"],
            "case_id": result["case_id"],
            "run_id": result["run_id"],
        })
        lines.append(f"agent_eval_score{{{result_labels}}} {result['score']}")
        lines.append(f"agent_eval_passed{{{result_labels}}} {bool_metric(result.get('passed'))}")
        lines.append(f"agent_eval_hard_failures{{{result_labels}}} {len(result.get('hard_failures', []))}")

        safety = result.get("subscores", {}).get("safety_and_permissions")
        if safety and safety.get("status") == "scored":
            lines.append(f"agent_eval_safety_score{{{result_labels}}} {safety.get('score', 0)}")
    return lines


def render_lifecycle_eval_metrics(results: list[dict[str, Any]]) -> list[str]:
    lines = []
    for result in [item for item in results if item.get("kind") == "AgentLifecycleEvalResult"]:
        result_labels = labels({
            "case_id": result["case_id"],
            "run_id": result["run_id"],
            "workflow_name": result.get("workflow_name", "{{WORKFLOW_NAME}}"),
        })
        lines.append(f"agent_lifecycle_eval_score{{{result_labels}}} {result['score']}")
        lines.append(f"agent_lifecycle_eval_passed{{{result_labels}}} {bool_metric(result.get('passed'))}")
        lines.append(f"agent_lifecycle_eval_hard_failures{{{result_labels}}} {len(result.get('hard_failures', []))}")
        for name, subscore in result.get("subscores", {}).items():
            if subscore.get("status") == "scored":
                subscore_labels = f'{result_labels},dimension="{prometheus_label_value(name)}"'
                lines.append(f"agent_lifecycle_eval_subscore{{{subscore_labels}}} {subscore.get('score', 0)}")
    return lines


def render_prometheus_metrics(results: list[dict[str, Any]]) -> str:
    lines = [
        "# HELP agent_eval_score Deterministic kagent agent eval score.",
        "# TYPE agent_eval_score gauge",
        "# HELP agent_eval_passed Whether a deterministic kagent agent eval passed.",
        "# TYPE agent_eval_passed gauge",
        "# HELP agent_eval_hard_failures Deterministic kagent agent eval hard failure count.",
        "# TYPE agent_eval_hard_failures gauge",
        "# HELP agent_lifecycle_eval_score End-to-end kagent incident lifecycle eval score.",
        "# TYPE agent_lifecycle_eval_score gauge",
        "# HELP agent_lifecycle_eval_passed Whether an end-to-end lifecycle eval passed.",
        "# TYPE agent_lifecycle_eval_passed gauge",
        "# HELP agent_lifecycle_eval_hard_failures End-to-end lifecycle eval hard failure count.",
        "# TYPE agent_lifecycle_eval_hard_failures gauge",
        "# HELP agent_lifecycle_eval_subscore End-to-end lifecycle eval subscore by dimension.",
        "# TYPE agent_lifecycle_eval_subscore gauge",
    ]
    lines.extend(render_agent_eval_metrics(results))
    lines.extend(render_lifecycle_eval_metrics(results))
    lines.append("")
    return "\n".join(lines)
