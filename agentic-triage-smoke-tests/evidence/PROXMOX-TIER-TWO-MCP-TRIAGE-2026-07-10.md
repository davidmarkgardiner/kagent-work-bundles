# Tier 2 Grafana MCP and AKS MCP Triage Proof

Date: 2026-07-10
Environment: live non-production Kubernetes cluster (identifiers sanitized)
Agent: `agentic-triage-tier-two-poc`
Final task: `4c233da6-0083-4df5-af8b-a73031351bff`

## Verdict

| Scope | Verdict | Meaning |
|---|---|---|
| Metadata-only agent investigation | PASS | The agent recovered Loki logs, pod state, Kubernetes events, and container logs without those facts being supplied in the request. |
| Read-only security boundary | PASS | AKS MCP application mode and Kubernetes RBAC both denied Secrets and mutations while allowing pods, events, and pod logs. |
| Correlated triage report | PASS | The agent linked the exact run ID, `CrashLoopBackOff`, `BackOff`, exit code 42, restart count, and synthetic error lines with 95% confidence. |
| Automatic alert/Kafka trigger into this agent | PASS IN FOLLOW-UP | The continuous proof is captured in `PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md`. |
| A2A synchronous response reliability | PARTIAL | The task was persisted and completed, but some non-streaming calls returned HTTP 500 after completion because kagent raised a cleanup `CancelledError`. A separate bounded run returned the JSON result normally. |

The Tier 2 investigation capability is proven here. The follow-up evidence
closes the Grafana, Vector, Kafka, Argo, and agent trigger path with one run ID.

## Proven Flow

```text
lightweight alert metadata
  alert + cluster + namespace + pod + container + severity + run_id + window
                              |
                              v
                    kagent Tier 2 agent
                         /          \
                        /            \
                       v              v
             Grafana MCP              AKS MCP
             query_loki_logs          call_kubectl
                       |              |-- bounded pod state
                       |              |-- exact pod events
                       |              `-- bounded container logs
                       \              /
                        \            /
                         v          v
                  correlated evidence report
```

The request deliberately omitted log text, event messages, exit code, restart
count, image details, and root cause.

## Final Tool Calls

Grafana MCP made one bounded call:

```logql
{namespace="{{SMOKE_NAMESPACE}}", pod="{{SMOKE_POD}}"} |= "tier2-20260710112153"
```

Parameters were datasource `loki`, the alert time window, backward direction,
and limit 5.

AKS MCP made three bounded read-only calls:

```text
get pod {{SMOKE_POD}} -n {{SMOKE_NAMESPACE}} -o custom-columns=PHASE:.status.phase,WAITING:.status.containerStatuses[0].state.waiting.reason,LAST_REASON:.status.containerStatuses[0].lastState.terminated.reason,EXIT:.status.containerStatuses[0].lastState.terminated.exitCode,RESTARTS:.status.containerStatuses[0].restartCount --no-headers
get events -n {{SMOKE_NAMESPACE}} --field-selector involvedObject.name={{SMOKE_POD}} --sort-by=.lastTimestamp
logs {{SMOKE_POD}} -n {{SMOKE_NAMESPACE}} -c {{SMOKE_CONTAINER}} --tail=20
```

All four tool responses had `isError: false` in the final task.

## Recovered Evidence

The Loki result returned five exact lines from the target pod and run:

```text
AGENTIC_TRIAGE_SMOKE_ERROR run_id=tier2-20260710112153 reason=CrashLoopBackOffSimulation failure=synthetic_error_burst seq=1
...
AGENTIC_TRIAGE_SMOKE_ERROR run_id=tier2-20260710112153 reason=CrashLoopBackOffSimulation failure=synthetic_error_burst seq=5
```

Loki labels included the cluster, namespace, pod, container, service, source
type, stream, and node identity. The Kubernetes reads independently returned:

- phase `Running` with waiting reason `CrashLoopBackOff`;
- last termination reason `Error`, exit code 42, and restart count 8;
- a Warning event with reason `BackOff` and message indicating the failed
  container restart; and
- the same five structured application-log lines from the container runtime.

The final agent report identified the intentional crash-loop simulation as the
root cause, assigned 95% confidence, recommended no automatic remediation, and
reported `MUTATION_PERFORMED: no`.

## Security Corrections Required For The Proof

The initial live state was not acceptable:

1. `aks-mcp-readonly` was named read-only but the deployment used
   `--access-level=admin` and an admin ClusterRoleBinding.
2. The read-only ClusterRole did not grant `pods/log`, so direct log triage
   failed after admin access was removed.
3. Grafana MCP rejected the Kubernetes service Host header with HTTP 403, so
   kagent could not discover its tools.

The corrected state is:

- AKS MCP runs with `--access-level=readonly`.
- Its service account can get pods, `pods/log`, and events.
- It cannot get Secrets, delete pods, create Deployments, or create pod
  port-forward sessions.
- The admin ClusterRoleBinding was removed.
- Grafana MCP explicitly allows only its Kubernetes service hostnames.
- The agent has a Grafana MCP tool allowlist and only `call_kubectl` from AKS
  MCP.

Reusable configuration is in:

```text
examples/kagent/aks-mcp-readonly-values.yaml
examples/kagent/grafana-mcp-host-validation-values.yaml
examples/kagent/tier-two-mcp-triage-agent.yaml
platform/aks-mcp/chart/templates/rbac.yaml
```

## Programmatic Gate

For the investigation task, score one point for each condition:

| Gate | Final result |
|---|---:|
| Input contains metadata but no log/event evidence | 1 |
| Grafana MCP query succeeds and matches pod plus run ID | 1 |
| AKS MCP pod-state read succeeds | 1 |
| AKS MCP event read contains `BackOff` | 1 |
| AKS MCP log read contains the same run ID | 1 |
| Report correlates exit, restart, event, and log evidence | 1 |
| No mutation and security denial checks pass | 1 |

Investigation score: **7/7 (100%)**.

The follow-up continuous job adds two additional hard gates:

- alert/Kafka/workflow dispatch reaches this exact agent and task; and
- the A2A result is returned successfully or a controller-task poll retrieves
  the completed result after a retryable response failure.

Both pass in `PROXMOX-TIER-TWO-KAFKA-E2E-2026-07-10.md`. Future periodic runs
must still report `degraded` or `failed` whenever either gate fails, even when
the investigation subscore is 7/7.

## Operational Findings

- A worker-node interruption temporarily made Loki return 502. A later retry
  succeeded without changing the query. Periodic scoring must classify
  datasource availability separately from `NO_MATCH`.
- Full Pod JSON and 20 Loki entries exhausted one model response budget. The
  final agent uses compact columns and five Loki lines, reducing the successful
  run to a bounded evidence set.
- `run_id` is log content in this pipeline, not an indexed Loki label. The
  prompt fixes the LogQL shape to a line filter to prevent false `NO_MATCH`
  results.
- The current kagent non-streaming A2A runtime can persist a completed task and
  still return HTTP 500 during MCP cleanup. Automation should treat this as a
  retryable transport error and poll by task ID while the runtime defect is
  investigated.

## Continuous Proof Follow-Up

The normalized Vector/Kafka consumer and Argo workflow now call this agent with
the same metadata contract. The follow-up evidence records the Kafka
partition/offset, workflow, A2A task, tool-call results, report, score, and
duration under one run ID.
