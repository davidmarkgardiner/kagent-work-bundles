# Data Storage, Access, Retention, And Traceability

## Data Classes

| Data | Example | Storage target | Access |
| --- | --- | --- | --- |
| Raw workflow evidence | unsanitized logs, traces, tool output | restricted workflow artifacts or source systems | smallest operational group only |
| Sanitized marker evidence | `HITL_STATUS: resumed`, `VERIFICATION_PASSED: yes` | workflow output parameter or artifact | evaluator and platform SRE |
| Normalized lifecycle run JSON | `AgentLifecycleRun` | workflow artifact, replay store, ticket attachment if sanitized | platform SRE, agent owner |
| Eval result JSON | `AgentLifecycleEvalResult` | artifact store and audit store | platform SRE, security/audit |
| Markdown summary | human-readable report | ticket comment/attachment or artifact | on-call, agent owner, platform SRE |
| Prometheus metrics | `agent_lifecycle_eval_score` | metrics backend | dashboard viewers by role |
| Dashboard panels | score trends and hard failures | Grafana | role-based viewer/editor/admin |

## Metric Label Rules

Allowed labels:

```text
agent
case_id
run_id
workflow_name
dimension
stable environment label added by publisher
stable team/service label added by publisher
```

`run_id` and full `workflow_name` are acceptable for per-run textfile, CI, and
artifact exports. For a long-lived Prometheus scrape endpoint, aggregate these
or move per-run identifiers into logs/exemplars to avoid unbounded cardinality.

Forbidden labels:

```text
prompt text
final answer text
raw logs
GitLab ticket body/title
real ticket URL
private IPs
subscription IDs
tenant IDs
tokens or API keys
high-cardinality trace/log content
```

## RBAC Boundaries

Evaluation should score evidence, not perform remediation.

| Capability | Evaluation step | Remediation step | Ticket step |
| --- | --- | --- | --- |
| Read sanitized workflow evidence | Yes | Optional | Optional |
| Read ConfigMap scorer scripts | Yes | No | No |
| Mutate Kubernetes workloads | No | Yes, narrow and HITL-gated | No |
| Read secrets | No | Only if explicitly required | Only GitLab token if needed |
| Write GitLab ticket | Prefer no | No | Yes |
| Publish metrics/report outputs | Yes | No | Optional |

The current Argo evaluator manifest ships a dedicated `agent-lifecycle-eval`
ServiceAccount with only `workflowtaskresults.argoproj.io` `create`/`patch`
permissions for Argo output reporting. It does not grant ConfigMap, Secret,
workload, apply, delete, or ticket-system permissions.

## Retention

| Data | Recommended retention | Reason |
| --- | ---: | --- |
| Raw traces/logs | short | Sensitive and high-volume. |
| Sanitized lifecycle run JSON | medium | Replay and regression testing. |
| Eval result JSON | medium to long | Audit and score history. |
| Markdown summary | ticket/artifact lifetime | Human review and incident history. |
| Prometheus metrics | standard metrics retention | Trend and alerting. |
| Dashboard snapshots | optional | Review material only. |

## Traceability Fields

Every lifecycle run should preserve these sanitized identifiers:

```text
run_id
case_id
incident_id
workflow_name
trace_id when available
agent names
ticket id when safe
approval id when safe
completed_at
score
passed
hard_failures
```

Do not store raw private URLs or tokens. Use IDs, placeholders, or links only in
restricted systems.

## Audit Trail

For a failed lifecycle eval, the agent/workflow should produce:

```text
EVAL_SCORE:
EVAL_PASSED:
HARD_FAILURES:
MISSING_EVIDENCE:
WORKFLOW_NAME:
RUN_ID:
TICKET_ID:
REVIEW_MANAGER_ROUTE:
NEXT_ACTION:
```

The current implementation emits this as a sanitized review-route payload from
`scripts/route-lifecycle-review.py`. Work environments can wire that payload to
a real review-manager agent, issue, or ticket workflow after local approval.

For production gating:

- keep ticket open when eval fails
- attach or link sanitized eval summary
- record human override if ticket is manually closed
- include approver, reason, workflow, ticket id, and follow-up owner

## Evidence Verification Commands

Offline:

```bash
python3 observability/agent-evals/scripts/summarize-agent-scores.py \
  --results-dir observability/agent-evals/results/sample \
  --summary-md /tmp/kagent-agent-eval-summary.md \
  --metrics /tmp/kagent-agent-eval.prom
```

Online manifest render:

```bash
kubectl kustomize observability/agent-evals
```

Metric contract:

```bash
rg "agent_lifecycle_eval_score|agent_lifecycle_eval_hard_failures" /tmp/kagent-agent-eval.prom
```
