# Proxmox Alloy Kubernetes Events To Loki Smoke - 2026-07-09

## Scope

This evidence records a live Kubernetes event exporter proof:

```text
Kubernetes FailedScheduling event
-> Alloy loki.source.kubernetes_events
-> Loki
-> Grafana Loki alert rule
-> Grafana webhook contact point
-> smart-triage Argo Events EventSource
-> smart-triage Workflow
-> HITL resume
-> lifecycle score
```

Environment-specific names, URLs, and cluster identifiers are sanitized.

## Live Changes

- Updated `{{MONITORING_NAMESPACE}}/ConfigMap alloy-k8s-events-config`.
- Kept the existing Kafka/OpenTelemetry branch in place.
- Added a parallel `loki.write` branch to `http://{{LOKI_GATEWAY_SERVICE}}.{{MONITORING_NAMESPACE}}.svc/loki/api/v1/push`.
- Expanded `loki.source.kubernetes_events` to watch:
  - `{{OLD_EVENT_SMOKE_NAMESPACE}}`
  - `{{SMOKE_NAMESPACE}}`
- Added namespace-scoped RBAC in `{{SMOKE_NAMESPACE}}` for ServiceAccount `{{MONITORING_NAMESPACE}}/alloy-k8s-events`.
- Lowered the live Alloy pod resource requests to fit the current dev-cluster worker capacity.

The live Alloy pod loaded the config and logged:

```text
node_id=loki.write.local_loki
watching events for namespace {{OLD_EVENT_SMOKE_NAMESPACE}}
watching events for namespace {{SMOKE_NAMESPACE}}
```

Existing Kafka export was not fixed in this run. It still reported SASL authentication failures. This proof is for the Loki branch.

## Event Generation

Created an intentionally unschedulable pod:

```text
namespace={{SMOKE_NAMESPACE}}
pod=event-smoke-unschedulable-loki
nodeSelector={{IMPOSSIBLE_NODE_SELECTOR}}
```

Kubernetes produced:

```text
Warning FailedScheduling pod/event-smoke-unschedulable-loki
```

## Loki Proof

Query:

```logql
{job="kubernetes-events", namespace="{{SMOKE_NAMESPACE}}", event_reason="FailedScheduling"}
|= "event-smoke-unschedulable-loki"
```

Loki returned one event with labels:

```text
job=kubernetes-events
namespace={{SMOKE_NAMESPACE}}
event_reason=FailedScheduling
event_type=Warning
pipeline=alloy-k8s-events-kafka-loki
payload_type=kubernetes-event
source=alloy
```

The log payload included:

```json
{
  "kind": "Pod",
  "name": "event-smoke-unschedulable-loki",
  "reason": "FailedScheduling",
  "type": "Warning"
}
```

## Grafana Alert Proof

Created or verified Grafana contact point:

```text
name=smart-triage-webhook
url=http://{{SMART_TRIAGE_EVENTSOURCE_SERVICE}}.{{ARGO_EVENTS_NAMESPACE}}.svc.cluster.local:12000/alerts
```

Added a narrow Grafana notification policy route:

```text
route_to = smart-triage -> smart-triage-webhook
```

Created Grafana Loki alert rule:

```text
uid=agentic-event-failedscheduling-loki
title=AgenticTriageEventFailedSchedulingLokiSmoke
folder=Agentic Triage Smoke
datasource=Loki
receiver=smart-triage-webhook
```

Rule query after cleanup tuning:

```logql
sum(count_over_time(
  {job="kubernetes-events", namespace="{{SMOKE_NAMESPACE}}", event_reason="FailedScheduling"}
  |= "event-smoke-unschedulable-loki"
[1m]))
```

The rule fired with:

```text
state=Alerting
value=1
labels:
  alertname=AgenticTriageEventFailedSchedulingLokiSmoke
  namespace={{SMOKE_NAMESPACE}}
  route_to=smart-triage
  source_type=event
  triage=true
```

After deleting the unschedulable pod and reducing the rule evaluation range to 60 seconds, Grafana returned:

```text
state=Normal (NoData)
```

## Webhook And Workflow Proof

The smart-triage EventSource received the Grafana webhook:

```text
eventSourceName=smart-triage-alertmanager
endpoint=/alerts
Succeeded to publish an event
```

The smart-triage Sensor created a workflow:

```text
triggerName=smart-triage-fanout-workflow
Successfully processed trigger
```

Workflow:

```text
name=smart-triage-alert-dzksn
phase=Succeeded
```

Normalized payload included:

```text
ALERT_SOURCE: alertmanager
ALERT_NAME: AgenticTriageEventFailedSchedulingLokiSmoke
NAMESPACE: {{SMOKE_NAMESPACE}}
```

The workflow reached HITL, was resumed, and lifecycle eval passed:

```text
HITL_STATUS: resumed
VERIFICATION_PASSED: yes
SMART_TRIAGE_PATTERN: proven
score=1.0 passed=true
```

## Important Caveat

The existing smart-triage WorkflowTemplate still emits synthetic specialist evidence for several agents, including Kubernetes, Grafana, trace, policy, and GitOps. This run proves the live ingestion, Grafana alerting, webhook routing, workflow fan-out, HITL, and scoring path. It does not prove that every specialist queried live backing systems for this specific event.

The next implementation step is to replace those synthetic specialist blocks with source-backed tool calls that use the normalized labels from the Grafana alert, especially `namespace`, `event_reason`, `source_type`, and object identity.

## Cleanup

- Deleted `{{SMOKE_NAMESPACE}}/Pod event-smoke-unschedulable-loki`.
- Grafana Loki alert returned to `Normal (NoData)`.
- Workflows created during the proof were allowed to complete.

## Cutover Implication

This is enough to say Alloy can export Kubernetes events into Loki and Grafana can alert on those event logs into the same smart-triage EventSource. It is not enough to retire all direct Kubernetes-event-to-Argo paths globally.

Retirement gate:

- repeat this proof for each target namespace allowlist;
- add excluded-namespace negative tests;
- replace synthetic specialist evidence;
- add periodic smoke scoring and alerting for exporter freshness, Grafana alert state, EventSource delivery, and workflow completion.
