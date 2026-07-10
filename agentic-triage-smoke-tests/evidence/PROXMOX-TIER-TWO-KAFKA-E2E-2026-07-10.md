# Tier 2 Grafana to Kafka to MCP Continuous Proof

Date: 2026-07-10
Environment: live non-production Kubernetes cluster (identifiers sanitized)
Run ID: `tier2e2e-20260710124542`
Workflow: `agentic-triage-tier-two-whrc5`
kagent task: `3698009c-a847-4699-a08a-289fc35c41b9`

## Verdict

**PASS: 7/7.** One run ID was preserved through the complete path:

```text
synthetic pod error
  -> pod stdout
  -> Loki
  -> scheduled Grafana LogQL evaluation
  -> firing Grafana alert
  -> Grafana webhook contact point
  -> Vector normalization
  -> Kafka normalized topic
  -> Argo Events Kafka EventSource
  -> Argo Sensor
  -> dedicated Tier 2 Workflow
  -> kagent Agent
  -> Grafana MCP plus read-only AKS MCP
  -> deterministic 7/7 score
```

The request delivered to kagent contained alert metadata but no log lines,
Kubernetes event output, exit code, restart count, image details, or root cause.

## Detection And Delivery Evidence

The run-scoped Grafana rule was healthy and firing:

```text
state: firing
health: ok
route_to: vector-kafka
run_id: tier2e2e-20260710124542
source_type: logs
```

The rule evaluated this LogQL pattern against Loki:

```logql
sum by (cluster,namespace,pod,container,service_name,node_name,reason,failure,run_id) (
  count_over_time(
    {namespace="{{SMOKE_NAMESPACE}}",source_type="logs"}
      |= "AGENTIC_TRIAGE_SMOKE_ERROR"
      | logfmt
      | run_id="tier2e2e-20260710124542" [5m]
  )
)
```

The alert used the dedicated Vector webhook receiver. Vector normalized the
payload and published it to the normalized alert topic. The Kafka EventSource
recorded a successful event publication from partition 4, offset 1. The Sensor
then recorded `Successfully processed trigger 'agentic-triage-tier-two'` and
created the workflow in the `argo` namespace.

The workflow labels independently identify the Kafka path:

```text
event-source=vector
events.argoproj.io/sensor=vector-alertmanager-triage
events.argoproj.io/trigger=agentic-triage-tier-two
workflows.argoproj.io/phase=Succeeded
```

Private Kafka endpoints are intentionally omitted from this public evidence.

## Workflow Evidence

The dedicated workflow completed in 56 seconds:

| Node | Result |
|---|---|
| `normalize-alert` | Succeeded |
| `investigate` | Succeeded |
| `score` | Succeeded |
| Workflow | Succeeded |

The normalized metadata retained the alert name, status, cluster, namespace,
pod, container, service, severity, source type, run ID, alert start time, and
fingerprint.

The score output was:

```json
{
  "status": "passed",
  "score": 7,
  "max_score": 7,
  "task_id": "3698009c-a847-4699-a08a-289fc35c41b9",
  "transport": "direct"
}
```

## MCP Investigation Evidence

The persisted kagent task completed with four successful tool calls and no
tool errors:

1. Grafana MCP `query_loki_logs` for the exact namespace, pod, run ID, and
   bounded 15-minute window, limit 5.
2. AKS MCP compact pod-state query.
3. AKS MCP exact pod-event query.
4. AKS MCP bounded container-log query.

The agent recovered:

- five Loki lines containing the exact run ID, synthetic reason, failure, and
  sequence 1 through 5;
- pod waiting reason `CrashLoopBackOff`;
- last termination reason `Error`, exit code 42, and restart count 6;
- a Warning `BackOff` event; and
- matching container logs through AKS MCP.

It correlated these observations into the synthetic crash-loop root cause,
reported 95% confidence, and returned `MUTATION_PERFORMED: no`.

Model usage for the successful investigation was 6,424 total tokens. This is a
bounded POC result, not yet a production cost target.

## Deterministic Score

The workflow awards one point for each required gate:

| Gate | Result |
|---|---:|
| Metadata contains a run ID | 1 |
| Agent completion marker | 1 |
| Grafana MCP Loki call reported | 1 |
| AKS MCP pod-state call reported | 1 |
| AKS MCP event call reported | 1 |
| AKS MCP log call reported | 1 |
| No-mutation marker | 1 |

The scorer subtracts a point when Loki reports `NO_MATCH`, a failed query, or
an HTTP 5xx response. The workflow fails unless the final score is exactly 7.

## Negative Gate Proof

The immediately preceding workflow used the alert firing time as the Loki
query start, after the logs that caused the alert. The agent correctly returned
`LOKI_EVIDENCE: NO_MATCH`; the scorer produced 6/7 and the workflow failed.

The final workflow passes an explicit 15-minute evidence window. This closes
the semantic mismatch between a scheduled Grafana lookback query and the later
alert firing timestamp.

## A2A Recovery

kagent rejects a caller-provided task ID for a new task with JSON-RPC error
`-32001`. The workflow therefore supplies only a deterministic context ID.

If the synchronous response is not usable, the workflow polls:

```text
/api/sessions/<context-id>/tasks?user_id=A2A_USER_<context-id>
```

It selects the completed session task and records its server-generated task
ID. The session lookup was verified against the successful task. The final
7/7 run returned directly, so a post-persistence HTTP 500 recovery remains a
fault-injection test rather than an observed condition in the passing run.

## Durable Assets

```text
examples/argo/tier-two-mcp-triage-workflow-template.yaml
examples/kagent/tier-two-mcp-triage-agent.yaml
examples/kagent/aks-mcp-readonly-values.yaml
examples/kagent/grafana-mcp-host-validation-values.yaml
examples/grafana/source-type-alert-rules.yaml
observability/vector/homelab/vector-http-receiver-to-kafka.yaml
observability/vector/manifests/02-argo-alertmanager-triage-topic.yaml
a2a/smart-triage-fanout-demo/workflow-template.yaml
```

## Periodic Use

For each scheduled run, generate a unique run ID, create an approved synthetic
failure, and use a run-scoped rule or equivalent query label. A green periodic
result requires all of the following under that same run ID:

- Grafana rule healthy and firing;
- Kafka EventSource event ID captured;
- Sensor-created workflow captured;
- workflow phase `Succeeded`;
- score 7/7;
- kagent task state `completed`;
- four successful MCP tool responses;
- no mutation marker; and
- cleanup completed.

Treat missing Loki evidence, datasource 5xx responses, MCP errors, workflow
timeouts, and score below 7 as failures. Do not report green from pod readiness
or alert firing alone.
