#!/usr/bin/env python3
"""Shared report rendering helpers for agent and chaos evals."""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: str | os.PathLike[str], payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_agent_eval_markdown(result: dict[str, Any]) -> str:
    hard_failures = result.get("hard_failures", [])
    warnings = result.get("warnings", [])
    lines = [
        "# Kagent Agent Eval Result",
        "",
        f"**Run:** `{result.get('run_id')}`",
        f"**Case:** `{result.get('case_id')}`",
        f"**Agent:** `{result.get('agent')}`",
        f"**Score:** `{result.get('score')}` / 1.0",
        f"**Passed:** `{str(result.get('passed')).lower()}`",
        f"**Trace:** `{result.get('trace_id', '{{TRACE_ID}}')}`",
        "",
        "## Sub-scores",
        "",
        "| Dimension | Status | Weight | Score | Reason |",
        "| --- | --- | ---: | ---: | --- |",
    ]

    for name, subscore in result.get("subscores", {}).items():
        score = subscore.get("score", "n/a")
        lines.append(
            f"| `{name}` | {subscore.get('status')} | {subscore.get('weight')} | {score} | {subscore.get('reason', '')} |"
        )

    lines += ["", "## Hard Failures", ""]
    if hard_failures:
        lines.extend(f"- {failure}" for failure in hard_failures)
    else:
        lines.append("- None")

    lines += ["", "## Warnings", ""]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")

    lines += ["", "## Tool Calls", ""]
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        for call in tool_calls:
            lines.append(f"- `{call.get('name')}`")
    else:
        lines.append("- None recorded")

    lines += [
        "",
        "## Public Repo Note",
        "",
        "This report is sanitized. Raw traces and environment-specific values are not committed.",
        "",
    ]
    return "\n".join(lines)


def render_chaos_recovery_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Kagent Chaos Recovery Eval Report",
        "",
        f"**Date:** {result.get('completed_at')}",
        "**Cluster:** local Kubernetes validation cluster (private address redacted)",
        f"**Recovery score:** `{result.get('recovery_score')}` / 1.0",
        "",
        "This report scores infrastructure recovery only. Agent diagnosis quality is scored separately by `observability/agent-evals/`.",
        "",
        "## Scenarios",
        "",
    ]

    for scenario in result.get("scenarios", []):
        lines += [
            f"### {scenario.get('scenario')}",
            f"- Recovery: **{scenario.get('recovery_seconds')}s**",
            f"- Stability score: **{scenario.get('workflow_stability')}**",
            f"- Notes: {scenario.get('notes')}",
            "",
        ]

    lines += [
        "## Public Repo Note",
        "",
        "The raw run log should stay local unless sanitized. This report preserves reproducible scoring without private host details.",
        "",
    ]
    return "\n".join(lines)


def render_lifecycle_eval_markdown(result: dict[str, Any]) -> str:
    hard_failures = result.get("hard_failures", [])
    warnings = result.get("warnings", [])
    lines = [
        "# Kagent Lifecycle Eval Result",
        "",
        f"**Run:** `{result.get('run_id')}`",
        f"**Case:** `{result.get('case_id')}`",
        f"**Incident:** `{result.get('incident_id')}`",
        f"**Score:** `{result.get('score')}` / 1.0",
        f"**Passed:** `{str(result.get('passed')).lower()}`",
        f"**Workflow:** `{result.get('workflow_name', '{{WORKFLOW_NAME}}')}`",
        f"**Trace:** `{result.get('trace_id', '{{TRACE_ID}}')}`",
        "",
        "## Sub-scores",
        "",
        "| Dimension | Status | Weight | Score | Reason |",
        "| --- | --- | ---: | ---: | --- |",
    ]

    for name, subscore in result.get("subscores", {}).items():
        score = subscore.get("score", "n/a")
        lines.append(
            f"| `{name}` | {subscore.get('status')} | {subscore.get('weight')} | {score} | {subscore.get('reason', '')} |"
        )

    lines += ["", "## Hard Failures", ""]
    if hard_failures:
        lines.extend(f"- {failure}" for failure in hard_failures)
    else:
        lines.append("- None")

    lines += ["", "## Warnings", ""]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")

    lines += ["", "## Lifecycle Evidence", ""]
    lifecycle = result.get("lifecycle", {})
    for key in [
        "alert_received",
        "triage_completed",
        "a2a_fanout_completed",
        "hitl_approved",
        "remediation_executed",
        "verification_passed",
        "ticket_updated",
    ]:
        lines.append(f"- `{key}`: `{str(lifecycle.get(key, False)).lower()}`")

    lines += [
        "",
        "## Public Repo Note",
        "",
        "This report is sanitized. Raw traces, tickets, and environment-specific values are not committed.",
        "",
    ]
    return "\n".join(lines)


def write_markdown(path: str | os.PathLike[str], markdown: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
