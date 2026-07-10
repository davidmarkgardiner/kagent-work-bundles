# LGTM Metrics-Only Coverage Assessment

## Summary

If the managed LGTM setup only supports metric-based alerting, the cluster is
not fully covered for agentic triage.

Estimated useful automated triage coverage:

```text
metrics-only alerting: 35-45%
```

Metrics are good at detecting that something is unhealthy. They are much weaker
at explaining what happened. For agentic triage, that matters because the agent
needs source evidence, not just a threshold breach.

## Coverage Estimate

| Area | Estimated coverage | Notes |
|---|---:|---|
| Infrastructure and pod health | 70-80% | Restarts, readiness, CPU, memory, OOM symptoms, pending pods, node pressure. |
| Application failure detection | 25-40% | Only good if the app exports useful error-rate/latency metrics. Exceptions without metrics are mostly invisible. |
| Kubernetes event context | 20-35% | Some events have metric symptoms, but raw event reason/message is missing. |
| Log-driven incidents | 0-15% | Unless logs are converted into metrics, log-only failures are not alertable. |
| Network and tracing context | 20-40% | Depends on ingress/service-mesh metrics. Without traces, causality is weak. |
| Agentic triage usefulness | 30-45% | The agent can detect unhealthy state, but often lacks evidence to explain why. |

## What Metrics-Only Can Catch

Metrics-only alerting can still catch useful symptoms:

```text
CrashLoopBackOff symptoms
container restarts
OOMKilled symptoms
pod pending or unschedulable via kube-state-metrics
node pressure
CPU or memory saturation
readiness failures
deployment replica mismatch
PVC pending
basic ingress 5xx or latency, if metrics exist
```

This is enough for basic platform health monitoring and some first-pass triage.
It is not enough for strong automated investigation.

## What Metrics-Only Misses Or Weakens

Without log, event, and trace alerting, the platform misses or weakens:

```text
application exceptions that do not change metrics quickly
Kubernetes Warning event message detail
image pull or registry auth reasons unless exposed as metrics
failed mounts with exact reason/message
DNS/connectivity errors visible only in logs
controller reconciliation errors from cert-manager, external-dns, Flux, etc.
network path and dependency causality
slow downstream dependency traces
misconfiguration messages from operators/controllers
```

This is the main risk for agentic triage. The alert can tell the agent that a
pod is unhealthy, but not why it is unhealthy. The agent then has to guess or
make additional queries that the managed service may not allow.

## Minimum Useful Alert Payload

Cluster name and pod name are not enough for triage.

At minimum, an alert should carry:

```text
cluster
namespace
workload or service
pod or object name
source_type
reason or error_class
short message or summary
timestamp or alert window
query, Explore URL, or enough fields to reconstruct the query
```

For events, the important fields are:

```text
source_type=events
reason=FailedScheduling|BackOff|FailedMount|ImagePullBackOff|Unhealthy
event_type=Warning
involved_object_kind
involved_object_name
namespace
message
first_seen / last_seen
```

For logs, the important fields are:

```text
source_type=logs
error_class or log_pattern
namespace
pod
container
sample_log_line or message summary
LogQL query or reconstructable query fields
time_window
```

## Fit-For-Purpose Position

Metrics-only LGTM can be a starting point, but it should not be considered
production-fit for agentic triage.

Use this position:

```text
Metrics-only alerting gives partial symptom detection, not full triage
coverage. For agentic triage we need logs, Kubernetes events, and traces where
available, either as first-class Grafana alerts or as queryable evidence the
agent can fetch during investigation.
```

If the managed LGTM service cannot provide Loki LogQL alerting, Kubernetes
event ingestion, useful metadata preservation, webhook routing, and a supported
automation/API path, treat that as a managed-service limitation. The next step
is to ask the LGTM team to close those gaps. If they cannot, the go/no-go
decision should include hosting or operating our own Grafana/LGTM stack where
we control Alloy, Loki, alert provisioning, notification policies, API/MCP
access, and smoke-test automation.

For the proposed bridge design for event reasons and pod log errors, see
`LGTM-EVIDENCE-BRIDGE-GAP.md`.
