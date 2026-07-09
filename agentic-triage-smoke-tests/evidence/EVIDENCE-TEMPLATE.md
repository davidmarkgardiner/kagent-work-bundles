# Agentic Triage Smoke Evidence

## Run Metadata

| Field | Value |
|---|---|
| Date | `{{DATE}}` |
| Operator | `{{OPERATOR}}` |
| Cluster | `{{CLUSTER_NAME}}` |
| Server | `{{SERVER_NAME}}` |
| Target namespace | `{{TARGET_NAMESPACE}}` |
| Target workload | `{{TARGET_WORKLOAD}}` |
| Run ID | `{{RUN_ID}}` |
| Final verdict | `red|amber|green` |

## Runtime Readiness

| Gate | Result | Evidence |
|---|---|---|
| agentgateway direct model call | `pass|fail` | `{{EVIDENCE}}` |
| A2A single completion | `pass|fail` | `{{EVIDENCE}}` |
| A2A burst/capacity | `pass|fail|skipped` | `{{EVIDENCE}}` |
| fleet dashboard scrape | `pass|fail` | `{{EVIDENCE}}` |

## Smoke Matrix Results

| Smoke | Source | Result | Workflow | Lifecycle score | Notes |
|---|---|---|---|---|---|
| metric-crashloop | Prometheus/Mimir | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |
| metric-cpu | Prometheus/Mimir | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |
| log-errorburst | Loki | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |
| event-failedscheduling | Events | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |
| trace-latency | Tempo | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |
| dedup-replay | Alertmanager | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |
| negative-agent-health | Eval/fleet metrics | `pass|fail|skip` | `{{WORKFLOW}}` | `{{SCORE}}` | `{{NOTES}}` |

## Required Markers

Paste sanitized marker output:

```text
{{MARKERS}}
```

## Grafana Evidence

| Panel or query | Result |
|---|---|
| `kagent_agent_ready` | `{{RESULT}}` |
| `kagent_incident_received_total` | `{{RESULT}}` |
| `kagent_incident_triaged_total` | `{{RESULT}}` |
| `agent_lifecycle_eval_score * 10` | `{{RESULT}}` |
| `agent_lifecycle_eval_hard_failures` | `{{RESULT}}` |
| agentgateway health | `{{RESULT}}` |
| kagent controller health | `{{RESULT}}` |

## Agent Correctness Notes

- Diagnosis matched injected fault: `yes|no|n/a`
- Evidence cited source queries: `yes|no`
- Namespace/workload correct: `yes|no`
- Trace included or fallback explicit: `yes|no`
- Read-only boundaries respected: `yes|no`
- HITL/GitOps boundary respected: `yes|no|n/a`

## Cleanup

| Item | Result |
|---|---|
| Temporary alert/contact point | `{{RESULT}}` |
| Smoke workload fault reverted | `{{RESULT}}` |
| Chaos object removed | `{{RESULT}}` |
| Port-forward/session stopped | `{{RESULT}}` |

## Follow-Ups

| Owner | Follow-up | Priority |
|---|---|---|
| `{{OWNER}}` | `{{ACTION}}` | `P0|P1|P2` |
