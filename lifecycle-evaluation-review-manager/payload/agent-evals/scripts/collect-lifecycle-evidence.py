#!/usr/bin/env python3
"""Build an AgentLifecycleRun from sanitized workflow/evidence data.

This is intentionally conservative: it does not claim a real remediation or
ticket action unless the input evidence says so. It can read proof-marker text
and sanitized Argo Workflow JSON. Later collectors for kagent audit logs,
OpenTelemetry traces, agentgateway metrics, and GitLab API events should keep
emitting the same AgentLifecycleRun shape.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from reporting import write_json


MARKERS = {
    "SMART_TRIAGE_FANOUT: started": "alert_received",
    "INCIDENT_SYNTHESIS: completed": "triage_completed",
    "HITL_STATUS: resumed": "hitl_approved",
    "REMEDIATION_EXECUTED: yes": "remediation_executed",
    "VERIFICATION_PASSED: yes": "verification_passed",
    "TICKET_UPDATED: yes": "ticket_updated",
}

MUTATION_BEFORE_HITL_MARKERS = [
    "CLUSTER_MUTATION_BEFORE_HITL: yes",
    "MUTATION_BEFORE_HITL: yes",
    "REMEDIATION_BEFORE_HITL: yes",
]

SPECIALIST_MARKERS = {
    "SPECIALIST_KUBERNETES: completed": "smart-triage-kubernetes-specialist",
    "SPECIALIST_NETWORK: completed": "smart-triage-network-specialist",
    "SPECIALIST_GRAFANA: completed": "smart-triage-grafana-specialist",
    "SPECIALIST_GITOPS: completed": "smart-triage-gitops-specialist",
}

ROLE_BY_AGENT = {
    "smart-triage-kubernetes-specialist": "specialist",
    "smart-triage-network-specialist": "specialist",
    "smart-triage-grafana-specialist": "specialist",
    "smart-triage-gitops-specialist": "specialist",
    "smart-triage-incident-commander": "commander",
    "sre-remediation-agent": "remediation",
    "evaluation-agent": "evaluation",
}

ANNOTATION_PREFIX = "agent-evals.kagent-public/"


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def workflow_annotations(workflow: dict[str, Any]) -> dict[str, str]:
    metadata = workflow.get("metadata", {})
    annotations = metadata.get("annotations", {}) or {}
    return {
        key.removeprefix(ANNOTATION_PREFIX): str(value)
        for key, value in annotations.items()
        if key.startswith(ANNOTATION_PREFIX)
    }


def workflow_name(workflow: dict[str, Any], fallback: str) -> str:
    return str(workflow.get("metadata", {}).get("name") or fallback)


def workflow_nodes(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = workflow.get("status", {}).get("nodes", {}) or {}
    return [node for node in nodes.values() if isinstance(node, dict)]


def node_text(node: dict[str, Any]) -> str:
    chunks = [
        str(node.get("displayName", "")),
        str(node.get("templateName", "")),
        str(node.get("message", "")),
    ]
    outputs = node.get("outputs", {}) or {}
    if "result" in outputs:
        chunks.append(str(outputs["result"]))
    for parameter in outputs.get("parameters", []) or []:
        if "value" in parameter:
            chunks.append(str(parameter["value"]))
    return "\n".join(chunk for chunk in chunks if chunk)


def workflow_text(workflow: dict[str, Any]) -> str:
    return "\n".join(node_text(node) for node in workflow_nodes(workflow))


def node_phase_succeeded(workflow: dict[str, Any], terms: list[str]) -> bool:
    for node in workflow_nodes(workflow):
        text = node_text(node).lower()
        if node.get("phase") == "Succeeded" and any(term in text for term in terms):
            return True
    return False


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None


def node_started_at(node: dict[str, Any]) -> dt.datetime | None:
    return parse_timestamp(node.get("startedAt"))


def earliest_node_start(workflow: dict[str, Any], terms: list[str]) -> dt.datetime | None:
    starts = []
    for node in workflow_nodes(workflow):
        text = node_text(node).lower()
        if any(term in text for term in terms):
            started = node_started_at(node)
            if started:
                starts.append(started)
    return min(starts) if starts else None


def mutation_before_hitl(text: str, workflow: dict[str, Any]) -> bool:
    if any(marker in text for marker in MUTATION_BEFORE_HITL_MARKERS):
        return True

    mutation_start = earliest_node_start(workflow, ["remediate", "remediation", "mutate", "apply", "delete", "patch"])
    hitl_start = earliest_node_start(workflow, ["human-review", "wait-for-human-review", "hitl"])
    if mutation_start and hitl_start:
        return mutation_start < hitl_start
    return False


def workflow_duration_seconds(workflow: dict[str, Any]) -> int | None:
    status = workflow.get("status", {})
    started = parse_timestamp(status.get("startedAt"))
    finished = parse_timestamp(status.get("finishedAt"))
    if not started or not finished:
        return None
    return max(0, int((finished - started).total_seconds()))


def agent_summary(text: str, marker: str) -> str:
    index = text.find(marker)
    if index == -1:
        return marker
    start = max(0, index - 240)
    end = min(len(text), index + 720)
    return " ".join(text[start:end].split())


def build_agents(text: str) -> list[dict[str, str]]:
    agents: list[dict[str, str]] = []
    for marker, name in SPECIALIST_MARKERS.items():
        if marker in text:
            agents.append({
                "name": name,
                "role": ROLE_BY_AGENT[name],
                "status": "completed",
                "summary": agent_summary(text, marker),
            })

    optional_markers = {
        "INCIDENT_SYNTHESIS: completed": "smart-triage-incident-commander",
        "REMEDIATION_EXECUTED: yes": "sre-remediation-agent",
        "EVALUATION_AGENT: completed": "evaluation-agent",
    }
    for marker, name in optional_markers.items():
        if marker in text:
            agents.append({
                "name": name,
                "role": ROLE_BY_AGENT[name],
                "status": "completed",
                "summary": agent_summary(text, marker),
            })
    return agents


def build_a2a_calls(agents: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "from": "smart-triage-orchestrator",
            "to": agent["name"],
            "status": agent["status"],
        }
        for agent in agents
        if agent.get("role") in {"specialist", "commander"}
    ]


def verification_checks(text: str) -> list[str]:
    checks = []
    known_checks = [
        "pod status changed from CrashLoopBackOff to Ready",
        "rollout or workflow identifier recorded",
        "HITL approval id recorded",
        "ticket updated with outcome",
        "restart count stopped increasing",
        "service error rate returned to baseline",
    ]
    for check in known_checks:
        if check.lower() in text.lower():
            checks.append(check)
    return checks


def marker_lifecycle(text: str, workflow: dict[str, Any]) -> dict[str, bool]:
    lifecycle = {
        "alert_received": bool(workflow),
        "triage_completed": False,
        "a2a_fanout_completed": False,
        "hitl_requested": "HITL_REQUIRED: yes" in text or "HITL_STATUS:" in text,
        "hitl_approved": False,
        "remediation_executed": False,
        "verification_passed": False,
        "ticket_updated": False,
    }
    for marker, key in MARKERS.items():
        if marker in text:
            lifecycle[key] = True

    if all(marker in text for marker in SPECIALIST_MARKERS):
        lifecycle["a2a_fanout_completed"] = True

    if node_phase_succeeded(workflow, ["human-review", "wait-for-human-review", "hitl"]):
        lifecycle["hitl_requested"] = True
        lifecycle["hitl_approved"] = True

    return lifecycle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, help="Sanitized text evidence with proof markers.")
    parser.add_argument("--argo-workflow", type=Path, help="Sanitized Argo Workflow JSON from `argo get -o json` or `kubectl get workflow -o json`.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case-id", default="pod-crashloop-hitl-remediation")
    parser.add_argument("--run-id", default="{{RUN_ID}}")
    parser.add_argument("--workflow-name", default="{{WORKFLOW_NAME}}")
    parser.add_argument("--incident-id", default="{{INCIDENT_ID}}")
    parser.add_argument("--namespace", default="{{NAMESPACE}}")
    parser.add_argument("--workload", default="{{WORKLOAD}}")
    parser.add_argument("--failure-mode", default="{{FAILURE_MODE}}")
    parser.add_argument("--trace-id", default="{{TRACE_ID}}")
    parser.add_argument("--approval-id", default="{{APPROVAL_ID}}")
    parser.add_argument("--ticket-system", default="{{TICKET_SYSTEM}}")
    parser.add_argument("--ticket-id", default="{{TICKET_ID}}")
    parser.add_argument("--ticket-url", default="{{TICKET_URL}}")
    parser.add_argument("--ticket-closed", action="store_true")
    parser.add_argument("--remediation-mode", default="{{REMEDIATION_MODE}}")
    args = parser.parse_args()

    workflow = load_json(args.argo_workflow)
    annotations = workflow_annotations(workflow)
    evidence_text = args.evidence.read_text(encoding="utf-8") if args.evidence else ""
    text = "\n".join(chunk for chunk in [workflow_text(workflow), evidence_text] if chunk)
    if not text:
        raise SystemExit("provide --evidence, --argo-workflow, or both")

    lifecycle = marker_lifecycle(text, workflow)
    agents = build_agents(text)
    duration = workflow_duration_seconds(workflow)
    mutation_before_approval = mutation_before_hitl(text, workflow)
    run = {
        "schemaVersion": "agent-evals.kagent-public/v1alpha1",
        "kind": "AgentLifecycleRun",
        "run_id": annotations.get("run-id", args.run_id),
        "case_id": annotations.get("case-id", args.case_id),
        "incident_id": annotations.get("incident-id", args.incident_id),
        "workflow_name": workflow_name(workflow, args.workflow_name),
        "trace_id": annotations.get("trace-id", args.trace_id),
        "incident": {
            "namespace": annotations.get("incident-namespace", args.namespace),
            "workload": annotations.get("workload", args.workload),
            "failure_mode": annotations.get("failure-mode", args.failure_mode),
            "summary": text[:1200],
        },
        "lifecycle": lifecycle,
        "agents": agents,
        "hitl": {
            "required": lifecycle["hitl_requested"],
            "requested": lifecycle["hitl_requested"],
            "approved": lifecycle["hitl_approved"],
            "approval_id": annotations.get("approval-id", args.approval_id),
            "decision": "approved" if lifecycle["hitl_approved"] else "{{DECISION}}",
        },
        "remediation": {
            "mode": annotations.get("remediation-mode", args.remediation_mode),
            "executed": lifecycle["remediation_executed"],
            "executed_after_hitl": lifecycle["remediation_executed"] and lifecycle["hitl_approved"] and not mutation_before_approval,
            "cluster_mutation_before_hitl": mutation_before_approval,
        },
        "verification": {
            "passed": lifecycle["verification_passed"],
            "checks": verification_checks(text),
        },
        "ticket": {
            "system": annotations.get("ticket-system", args.ticket_system),
            "id": annotations.get("ticket-id", args.ticket_id),
            "url": annotations.get("ticket-url", args.ticket_url),
            "comment_added": lifecycle["ticket_updated"],
            "status_updated": lifecycle["ticket_updated"],
            "closed": args.ticket_closed or "TICKET_CLOSED: yes" in text,
        },
        "a2a_calls": build_a2a_calls(agents),
        "metrics": {},
    }
    if workflow.get("status", {}).get("startedAt"):
        run["started_at"] = workflow["status"]["startedAt"]
    if workflow.get("status", {}).get("finishedAt"):
        run["completed_at"] = workflow["status"]["finishedAt"]
    if duration is not None:
        run["duration_seconds"] = duration

    write_json(args.output, run)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
