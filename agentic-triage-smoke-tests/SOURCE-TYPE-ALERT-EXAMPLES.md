# Source-Type Alert Examples

These examples show the expected full path for each Grafana-origin signal type:

```text
failure/event/log/trace signal -> Grafana alert rule -> webhook contact point
-> Argo Events EventSource -> smart-triage Workflow -> kagent specialists
-> smoke score and Grafana health metrics
```

`metric-crashloop` intake and `event-failedscheduling` via Alloy/Loki are
live-proven in the current Proxmox evidence. Trace fallback is live-proven as
`NO_TRACE`. Loki application logs remain blocked/not proven because the smoke
pod log marker did not reach Loki during the 2026-07-09 run.

## Shared Webhook Target

Use a test-only Grafana contact point that posts Alertmanager-compatible
payloads to the smart-triage EventSource:

```text
name: agentic-triage-smart-triage-webhook
url: http://{{SMART_TRIAGE_EVENTSOURCE_SERVICE}}.{{ARGO_EVENTS_NAMESPACE}}.svc.cluster.local:12000/alerts
```

Required alert labels for every source:

```text
cluster
namespace
workload
run_id
smoke
source_type
```

The same `run_id` and fingerprint must appear in the Grafana alert payload,
Argo Workflow labels, kagent output, score JSON, and dashboard metrics.

## Metric: CrashLoop

Failure setup:

```text
kubectl apply -f examples/k8s/crashloop-smoke-target.yaml
```

Grafana query:

```promql
kube_pod_container_status_terminated_reason{
  namespace="{{SMOKE_NAMESPACE}}",
  reason="Error"
} > 0
```

Webhook replay payload:

```text
examples/alertmanager-payloads/metric-crashloop.json
```

Required proof:

```text
Grafana state: Alerting
EventSource: request received and published
Workflow: smart-triage-alert-*
SPECIALIST_KUBERNETES: completed
SPECIALIST_GRAFANA: completed
agentic_triage_smoke_score >= 0.85
```

## Logs: Error Burst

Failure setup:

```text
emit at least five known error lines from the smoke workload in five minutes
```

Example log line:

```text
AGENTIC_TRIAGE_SMOKE_ERROR run_id={{RUN_ID}} smoke=log-errorburst failure=synthetic_error_burst
```

Grafana query:

```logql
sum by (namespace, pod, container) (
  count_over_time(
    {namespace="{{SMOKE_NAMESPACE}}", container="{{SMOKE_CONTAINER}}"}
    |= "AGENTIC_TRIAGE_SMOKE_ERROR"
    | json
    | run_id="{{RUN_ID}}"
  [5m])
) >= 5
```

Webhook replay payload:

```text
examples/alertmanager-payloads/log-errorburst.json
```

Required proof:

```text
Grafana state: Alerting
LogQL query and sample timestamp range captured
EventSource: request received and published
SPECIALIST_GRAFANA: completed
agent output cites log evidence and does not invent restart state
```

## Events: Failed Scheduling

Failure setup:

```text
create a smoke pod with an impossible node selector or resource request
```

For the longer-term Alertmanager cutover design and namespace targeting, see
`ALERTMANAGER-EVENT-ROUTING.md`.

Grafana query, when Kubernetes events are collected into Loki:

```logql
sum by (namespace, involved_object_name, reason) (
  count_over_time(
    {namespace="{{SMOKE_NAMESPACE}}", job=~".*event.*"}
    |= "FailedScheduling"
    |= "{{RUN_ID}}"
  [5m])
) > 0
```

Live-proven Alloy/Loki label shape:

```logql
sum(count_over_time(
  {job="kubernetes-events", namespace="{{SMOKE_NAMESPACE}}", event_reason="FailedScheduling"}
  |= "{{SMOKE_POD_NAME}}"
[1m]))
```

The 2026-07-09 proof used `SMOKE_POD_NAME=event-smoke-unschedulable-loki`,
Grafana rule `AgenticTriageEventFailedSchedulingLokiSmoke`, and workflow
`smart-triage-alert-dzksn`.

Prometheus/Mimir alternative, if kube-state-metrics event metrics are enabled:

```promql
sum by (namespace, reason, involved_object_name) (
  increase(kube_event_count{
    namespace="{{SMOKE_NAMESPACE}}",
    reason="FailedScheduling"
  }[5m])
) > 0
```

Webhook replay payload:

```text
examples/alertmanager-payloads/event-failedscheduling.json
```

Required proof:

```text
Grafana state: Alerting
event_reason=FailedScheduling survives normalization
EventSource: request received and published
SPECIALIST_KUBERNETES: completed
agent output stays namespace-scoped
```

## Traces: Latency

Failure setup:

```text
generate a high-latency request from an instrumented smoke workload
```

Grafana query, if span metrics are exported:

```promql
histogram_quantile(
  0.95,
  sum by (le, service_name) (
    rate(traces_spanmetrics_latency_bucket{
      service_name="{{SMOKE_SERVICE}}"
    }[5m])
  )
) > {{LATENCY_THRESHOLD_SECONDS}}
```

If the cluster has Tempo but not span metrics, use a Grafana trace-linked alert
that includes `trace_id` and a Tempo deeplink in annotations. If there is no
trace source, the trace smoke can only pass as explicit fallback:

```text
TRACE_FALLBACK: NO_TRACE
```

Webhook replay payload:

```text
examples/alertmanager-payloads/trace-latency.json
```

Required proof:

```text
Grafana state: Alerting
trace_id or TRACE_FALLBACK is present
EventSource: request received and published
SPECIALIST_TRACE: completed
agent output does not invent Tempo evidence
```
