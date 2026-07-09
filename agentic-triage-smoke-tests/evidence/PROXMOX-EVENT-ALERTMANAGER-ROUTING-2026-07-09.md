# Proxmox Event Alertmanager Routing Evidence - 2026-07-09

## Verdict

`green`

Kubernetes `FailedScheduling` symptom coverage was put in place through
Prometheus and Alertmanager, routed to the smart-triage Alertmanager webhook
EventSource, and verified through a successful smart-triage fan-out workflow.

This proves the replacement path for this event class:

```text
Kubernetes scheduling failure
-> kube-state-metrics unschedulable metric
-> PrometheusRule alert
-> AlertmanagerConfig webhook route
-> smart-triage EventSource
-> Sensor-created Argo Workflow
-> kagent smart-triage fan-out
-> HITL resume and lifecycle eval
```

It does not prove raw Kubernetes Warning events through `kube_event_count` or a
Loki event exporter. The live cluster exposed `kube_pod_status_unschedulable`,
but not `kube_event_count`.

## Runtime

| Field | Value |
|---|---|
| Cluster context | `{{CLUSTER_NAME}}` |
| Smoke namespace | `agentic-triage-event-smoke` |
| Smoke pod | `event-smoke-unschedulable` |
| Run ID | `triage-smoke-20260709-event-routing` |
| Alert | `AgenticTriageEventFailedSchedulingSmoke` |
| Workflow | `smart-triage-alert-k2tkp` |

## Live Resources Applied

```text
namespace/agentic-triage-event-smoke
prometheusrule.monitoring.coreos.com/agentic-triage-event-smoke-rules
alertmanagerconfig.monitoring.coreos.com/agentic-triage-event-smoke-webhook
pod/event-smoke-unschedulable
```

Important implementation detail: the first AlertmanagerConfig was created in
`monitoring`, which caused Prometheus Operator to add an automatic
`namespace="monitoring"` matcher. That could not match an alert whose
`namespace` label was `agentic-triage-event-smoke`. The working
AlertmanagerConfig is therefore created in `agentic-triage-event-smoke`.

## Failure Scenario

The smoke pod used an impossible node selector:

```text
nodeSelector:
  agentic-triage-smoke/nonexistent-node: "true"
```

Kubernetes event proof:

```text
Warning  FailedScheduling
0/3 nodes are available: control-plane taint and worker node selector mismatch
```

Prometheus signal proof:

```text
kube_pod_status_unschedulable{namespace="agentic-triage-event-smoke",pod="event-smoke-unschedulable"} 1
```

## Alertmanager Routing Proof

Generated Alertmanager route:

```text
receiver: agentic-triage-event-smoke/agentic-triage-event-smoke-webhook/smart-triage-event-smoke-webhook
matchers:
  - triage="true"
  - route_to="smart-triage"
  - namespace="agentic-triage-event-smoke"
```

Alertmanager active alert proof:

```text
alertname: AgenticTriageEventFailedSchedulingSmoke
namespace: agentic-triage-event-smoke
pod: event-smoke-unschedulable
run_id: triage-smoke-20260709-event-routing
source_type: events
receiver: agentic-triage-event-smoke/.../smart-triage-event-smoke-webhook
status: active
```

## EventSource And Sensor Proof

EventSource log:

```text
a request received, processing it...
Succeeded to publish an event
successfully dispatched the request to the event bus
```

Sensor log:

```text
creating the object...
Successfully processed trigger 'smart-triage-fanout-workflow'
triggeredBy=["alertmanager-alert"]
```

Workflow created:

```text
smart-triage-alert-k2tkp
```

## Workflow Proof

Workflow result:

```text
Status: Succeeded
Progress: 14/14
```

Normalize step:

```text
SMART_TRIAGE_FANOUT: started
ALERT_INGESTED: yes
INCIDENT_NORMALIZED: yes
ALERT_NAME: AgenticTriageEventFailedSchedulingSmoke
NAMESPACE: agentic-triage-event-smoke
POD: event-smoke-unschedulable
```

Specialist and final markers:

```text
SPECIALIST_KUBERNETES: completed
SPECIALIST_NETWORK: completed
SPECIALIST_GRAFANA: completed
SPECIALIST_GITOPS: completed
SPECIALIST_KNOWLEDGE: completed
SPECIALIST_DEPLOYMENT: completed
SPECIALIST_POLICY: completed
SPECIALIST_TRACE: completed
INCIDENT_SYNTHESIS: completed
HITL_STATUS: resumed
VERIFICATION_PASSED: yes
SMART_TRIAGE_PATTERN: proven
```

Lifecycle eval:

```text
score=1.0
passed=true
```

## Cleanup

The deliberately unschedulable pod was deleted after verification to stop
repeat notifications:

```text
pod "event-smoke-unschedulable" deleted
```

The smoke namespace, PrometheusRule, and AlertmanagerConfig were left in place
for future event-routing smoke runs. With no smoke pod present, no event smoke
alert remains active.

## Cutover Status

This proves that `FailedScheduling` event-class symptoms can flow through
Alertmanager/Grafana webhook into the same smart-triage EventSource. Before
retiring any broader Alloy/custom event bridge, repeat the same proof for the
target namespace allowlist and for any event classes that rely on raw event
records rather than kube-state-metrics symptom metrics.
