# Alertmanager Event Routing

## Target Architecture

The preferred steady-state path is:

```text
Kubernetes metrics/logs/events/traces
-> Prometheus/Mimir or Loki/Tempo
-> Grafana alerting or Alertmanager
-> smart-triage webhook EventSource
-> Argo Workflow
-> kagent specialists
```

If the work environment uses Vector and Kafka between Grafana/Alertmanager and
Argo Events, keep the same alert-source design and insert those transport hops:

```text
Grafana alerting or Alertmanager
-> Vector webhook receiver
-> Kafka topic
-> Kafka EventSource or consumer
-> smart-triage Sensor/Workflow
```

This means the legacy direct path:

```text
Kubernetes event stream -> Alloy/custom bridge -> Argo EventSource
```

can be turned off only after equivalent event coverage is proven through
Alertmanager-compatible alerts.

No extra event-processing product is required for the Loki-backed event route.
The required work is configuration: collect Kubernetes events with Alloy
`loki.source.kubernetes_events`, write them to Loki with useful labels, create
a Grafana LogQL alert over those labels, and route that alert to the existing
triage webhook path.

## Live Verification

The `FailedScheduling` symptom path was verified on 2026-07-09 with:

```text
PrometheusRule: agentic-triage-event-smoke-rules
AlertmanagerConfig: agentic-triage-event-smoke-webhook
Workflow: smart-triage-alert-k2tkp
Evidence: evidence/PROXMOX-EVENT-ALERTMANAGER-ROUTING-2026-07-09.md
```

That proof used `kube_pod_status_unschedulable`, because `kube_event_count` was
not exposed by the live cluster. It proves the scheduling-failure event class,
not raw Kubernetes Warning-event ingestion.

The raw Kubernetes event-to-Loki path was also verified on 2026-07-09 with:

```text
Alloy: loki.source.kubernetes_events -> loki.write
Loki label: job=kubernetes-events
Grafana rule: AgenticTriageEventFailedSchedulingLokiSmoke
Workflow: smart-triage-alert-dzksn
Evidence: evidence/PROXMOX-ALLOY-K8S-EVENTS-TO-LOKI-2026-07-09.md
```

That proof used Alloy to collect a real `Warning FailedScheduling` Kubernetes
event and write it to Loki before Grafana fired a LogQL alert into the same
smart-triage EventSource.

## What Counts As A Kubernetes Event Alert

Kubernetes events are short-lived API objects. Alertmanager does not consume
them directly. They must first be represented as one of these alertable signals:

- Prometheus/Mimir metrics, for example `kube_event_count` or
  `kube_pod_status_unschedulable`;
- Loki log records from an event exporter or Alloy event collection pipeline;
- a Grafana alert rule over either of those sources.

The current bundle has a metrics symptom alert for scheduling:

```promql
kube_pod_status_unschedulable{namespace=~"{{TARGET_NAMESPACE_REGEX}}"} > 0
```

That is enough to detect failed scheduling, but it is not the same as proving a
raw Kubernetes `Warning` event source unless the event exporter/Loki or
`kube_event_count` path is also captured.

The same distinction applies to logs. A Prometheus metric alert does not
automatically carry related Loki log lines. To make logs first-class triage
inputs, ensure pod logs are ingested into Loki and create Grafana LogQL alert
rules for the error patterns or smoke markers that should open triage.
Correlation from a metric alert to nearby logs/events is a separate enrichment
step that can be done by the triage agent or by a webhook enrichment service.

## Namespace Targeting

Yes, namespace targeting is possible and should be explicit in two places:

1. Alert rule expression, so only selected namespaces produce triage alerts.
2. Alertmanager or Grafana notification policy, so only selected alert payloads
   are routed to the smart-triage webhook.

Use an allowlist by default:

```text
{{TARGET_NAMESPACE_REGEX}} = whiskey|podinfo|cert-manager|external-dns
```

Avoid broad negative filters as the only control. They are useful for excluding
system namespaces, but an allowlist is safer for early rollout.

With Prometheus Operator `AlertmanagerConfig`, remember that the operator adds a
matcher for the namespace that owns the `AlertmanagerConfig`. Put the
`AlertmanagerConfig` in the namespace whose alerts it should route, or use a
central Alertmanager configuration path where namespace enforcement is
intentionally disabled and reviewed.

## Prometheus/Mimir Event Rules

If `kube_event_count` is available:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: agentic-triage-kubernetes-event-rules
  namespace: "{{MONITORING_NAMESPACE}}"
  labels:
    release: "{{PROMETHEUS_RELEASE_LABEL}}"
    app.kubernetes.io/part-of: agentic-triage
spec:
  groups:
    - name: agentic-triage-kubernetes-events
      interval: 30s
      rules:
        - alert: AgenticTriageKubernetesWarningEvent
          expr: |
            sum by (cluster, namespace, reason, involved_object_kind, involved_object_name) (
              increase(kube_event_count{
                namespace=~"{{TARGET_NAMESPACE_REGEX}}",
                type="Warning",
                reason=~"FailedScheduling|BackOff|FailedMount|ErrImagePull|ImagePullBackOff|Unhealthy"
              }[5m])
            ) > 0
          for: 1m
          labels:
            severity: warning
            triage: "true"
            route_to: agentic-triage
            source_type: events
          annotations:
            summary: "Kubernetes warning event in {{ $labels.namespace }}"
            description: "Reason {{ $labels.reason }} for {{ $labels.involved_object_kind }}/{{ $labels.involved_object_name }}."
```

If `kube_event_count` is not available, use symptom metrics for important event
classes:

```promql
kube_pod_status_unschedulable{namespace=~"{{TARGET_NAMESPACE_REGEX}}"} > 0
kube_pod_container_status_waiting_reason{namespace=~"{{TARGET_NAMESPACE_REGEX}}",reason=~"ImagePullBackOff|ErrImagePull|CrashLoopBackOff"} > 0
kube_pod_container_status_last_terminated_reason{namespace=~"{{TARGET_NAMESPACE_REGEX}}",reason="OOMKilled"} > 0
```

## Loki Event Rules

If Kubernetes events are collected into Loki, use a LogQL alert:

```logql
sum by (cluster, namespace, reason, involved_object_kind, involved_object_name) (
  count_over_time(
    {namespace=~"{{TARGET_NAMESPACE_REGEX}}", job=~".*event.*"}
    |~ "FailedScheduling|BackOff|FailedMount|ErrImagePull|ImagePullBackOff|Unhealthy"
  [5m])
) > 0
```

The exact labels depend on the event exporter. Before enabling this rule,
capture one known event in Explore and record the real label names.

For the live Alloy proof, the working labels were:

```text
job=kubernetes-events
namespace={{SMOKE_NAMESPACE}}
event_reason=FailedScheduling
event_type=Warning
payload_type=kubernetes-event
pipeline=alloy-k8s-events-kafka-loki
```

The live smoke rule used:

```logql
sum(count_over_time(
  {job="kubernetes-events", namespace="{{SMOKE_NAMESPACE}}", event_reason="FailedScheduling"}
  |= "event-smoke-unschedulable-loki"
[1m]))
```

Use a short evaluation window for periodic smoke rules. A long range query can
keep Grafana alerting on a historical event after the failure pod is deleted.

## Loki Log Rules

For application log smokes, the required path is:

```text
pod stdout/stderr -> Alloy or Promtail -> Loki -> Grafana LogQL alert
```

Use a deterministic smoke marker so the alert can be joined to the workflow:

```text
AGENTIC_TRIAGE_SMOKE_ERROR run_id={{RUN_ID}} smoke=log-errorburst failure=synthetic_error_burst
```

Example LogQL:

```logql
sum by (cluster, namespace, pod, container) (
  count_over_time(
    {namespace="{{SMOKE_NAMESPACE}}", container="{{SMOKE_CONTAINER}}"}
    |= "AGENTIC_TRIAGE_SMOKE_ERROR"
    |= "run_id={{RUN_ID}}"
  [5m])
) >= 5
```

Before enabling the alert, prove the marker is queryable in Loki Explore and
record the exact label set. If the marker exists in `kubectl logs` but not in
Loki, the failure is log shipping, not triage.

## Alertmanager Routing

Alertmanager can target namespaces using matchers:

```yaml
route:
  receiver: default-receiver
  group_by:
    - alertname
    - namespace
    - reason
  routes:
    - receiver: agentic-triage-webhook
      matchers:
        - triage = "true"
        - route_to = "agentic-triage"
        - namespace =~ "{{TARGET_NAMESPACE_REGEX}}"
      continue: true
receivers:
  - name: agentic-triage-webhook
    webhook_configs:
      - url: "http://{{SMART_TRIAGE_EVENTSOURCE_SERVICE}}.{{ARGO_EVENTS_NAMESPACE}}.svc.cluster.local:12000/alerts"
        send_resolved: true
        max_alerts: 50
```

Grafana notification policies can do the same with label matchers:

```text
triage = true
route_to = agentic-triage
namespace =~ {{TARGET_NAMESPACE_REGEX}}
source_type = events
```

## Cutover Gate

Do not disable the Alloy/custom event bridge until these checks are green:

- event exporter or Loki event ingestion is present and queryable;
- one `FailedScheduling` event in a target namespace fires through
  Grafana/Alertmanager to the smart-triage webhook;
- one excluded namespace does not route to smart triage;
- normalized incident contains `namespace`, `reason`, object kind/name, `run_id`,
  and `source_type=events`;
- kagent output cites the event source and stays namespace-scoped;
- the periodic smoke suite includes an event smoke and publishes source coverage
  as `events=proven`.
