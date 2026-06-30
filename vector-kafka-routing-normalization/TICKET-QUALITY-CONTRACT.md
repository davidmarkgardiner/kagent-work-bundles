# Ticket Quality Contract

The workflow should create or update a GitLab/ServiceNow record only when it has
useful evidence. A ticket that only repeats the alert name is not enough.

## Required Fields

| Field | Required content |
|---|---|
| Title | Alert name, namespace/service, severity |
| Summary | Human-readable problem statement |
| Route | `target_agent`, `route_key`, `routing_reason` |
| Source | Grafana alert rule UID, contact point, raw/normalized path |
| Evidence | logs, events, metrics, traces, dashboard/panel links |
| Workflow | Argo workflow name, phase, start/end time |
| Dedupe | `dedupe_key` and whether duplicates were suppressed |
| Safety | `automation_allowed`, HITL status, remediation mode |
| Recommendation | next action, owner, rollback or remediation suggestion |
| Outcome | open, deflected, remediated, escalated, closed |

## Deflection Tagging

Use one of these tags or fields:

```text
agentic-deflected
agentic-remediated
agentic-escalated
agentic-hitl-required
agentic-no-action
```

This allows dashboards to track whether ServiceNow/GitLab volume is decreasing
or whether the system is creating better evidence for unavoidable incidents.

## Acceptance Criteria

The ticket is acceptable when an SRE can understand:

- what fired
- why the platform routed it to that agent
- what evidence was gathered
- what action was recommended or taken
- whether a human approved any write-capable step
- where to inspect the dashboard and workflow
