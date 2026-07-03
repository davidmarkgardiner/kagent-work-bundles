# Rich Alert Context Contract

## Purpose

This document proves and defines how Grafana/Alertmanager should send enough
context for the triage agent to isolate the issue quickly. The goal is to avoid
weak records that only contain a generic alert name.

The target flow remains:

```text
Grafana-managed alert rule / Alertmanager notification
  -> Vector HTTP webhook receiver
  -> Vector filtering, enrichment, dedupe, and routing
  -> Kafka actionable topic
  -> Argo Sensor
  -> Argo Workflow
  -> triage agent or specialist agent
```

## Portable Parameters

The home-lab proof below uses `kind-argo-workflow`, `kube-system`, and `coredns`.
Do not copy those literally into the work environment. Map each parameter first,
then reuse the same steps. Keep secrets out of this file and out of alert
payloads.

| Parameter | Home-lab value | Work value to discover |
|---|---|---|
| `{{KUBE_CONTEXT}}` | `kind-argo-workflow` | Work events-cluster context |
| `{{GRAFANA_URL}}` | local Grafana OSS | Work Grafana base URL |
| `{{GRAFANA_DATASOURCE_UID}}` | test Prometheus | Work Prometheus/Mimir datasource UID |
| `{{GRAFANA_CONTACT_POINT}}` | `vector-payload-capture` | Existing Manager/Grafana contact point into Vector |
| `{{VECTOR_RECEIVER_URL}}` | temp webhook receiver | Existing Vector HTTP receiver URL/path |
| `{{TARGET_NAMESPACE}}` | `kube-system` | A safe, low-noise test namespace |
| `{{TARGET_WORKLOAD}}` | `coredns` | A safe workload with stable labels |
| `{{KAFKA_ACTIONABLE_TOPIC}}` | `observability.alerts.actionable.v1` | Work actionable topic (see KAFKA-TOPIC-DESIGN-README.md) |
| `{{ROUTE_DOMAIN}}` | `platform` | Work route domain for this signal |
| `{{TARGET_AGENT}}` | `aks-sre-triage-agent` | Work triage agent name |
| `{{RUNBOOK_ID}}` | `aks-dns-coredns-triage` | Work runbook id/url |

Discover these with `prompts/01-preflight-env-tools.md` and
`PREREQS-CHECKLIST.md` before firing anything. Prefer Grafana MCP for reads and
rule creation; use the provisioning API only as fallback.

## Minimum Viable Context

The agent does not need every field to be useful. Rank effort like this so a
work run is not blocked waiting for perfect data.

Must-have (agent cannot isolate without these):

```text
alert_name
cluster
namespace
pod or workload or service   (at least one resource anchor)
severity
status
```

Should-have (turns a generic alert into a triage-ready record):

```text
event_name
event_reason
description
route_domain
target_agent
dedupe_key
```

Nice-to-have (accelerates the agent but is not blocking):

```text
event_context
suggested_kubectl
suggested_log_query
suggested_promql
runbook_url
dashboard_url
recent_change_hint
```

If a must-have is missing, that is a stop condition. If a should-have or
nice-to-have is missing, record it in `normalization_gaps` and continue.

## What Was Proved In Home Lab

Verified on `kind-argo-workflow` with a real Grafana-managed alert rule and a
temporary webhook receiver shaped like the Vector HTTP input.

The alert was not a synthetic curl payload. Grafana evaluated the rule, fired
two alert instances, and delivered the notification through a webhook contact
point.

Verified delivery fields included:

```text
alerts[].labels.alertname: Vector rich payload proof - event context
alerts[].labels.cluster: kind-argo-workflow
alerts[].labels.namespace: kube-system
alerts[].labels.pod: coredns-...
alerts[].labels.job: coredns
alerts[].labels.service: coredns
alerts[].labels.event_name: CoreDNSAvailabilitySignal
alerts[].labels.event_reason: EndpointHealthCheckFiring
alerts[].labels.event_source: grafana_alert_rule
alerts[].labels.runbook_id: aks-dns-coredns-triage
alerts[].labels.route_domain: platform
alerts[].labels.target_agent: aks-sre-triage-agent
alerts[].labels.severity: warning
```

The webhook also delivered templated annotations for agent action:

```text
alerts[].annotations.summary:
  CoreDNS pod coredns-... is firing in namespace kube-system on cluster kind-argo-workflow

alerts[].annotations.description:
  Event CoreDNSAvailabilitySignal from coredns indicates pod coredns-... needs
  triage. Check recent rollout, pod restarts, logs, endpoints, DNS latency, and
  node health.

alerts[].annotations.event_context:
  event_name=CoreDNSAvailabilitySignal; event_reason=EndpointHealthCheckFiring;
  resource=kube-system/coredns-...; cluster=kind-argo-workflow; service=coredns

alerts[].annotations.suggested_kubectl:
  kubectl -n kube-system describe pod coredns-...

alerts[].annotations.suggested_log_query:
  {namespace="kube-system", pod="coredns-..."}
```

## Key Finding

Yes, the alerting path can pass event-style context to Vector and onward to the
triage agent, but the data must exist in the alert labels or annotations before
the webhook notification is sent.

Grafana/Alertmanager will pass rich labels and annotations. It will not invent
Kubernetes event fields that the alert rule did not query or annotate.

## Required Alert Rule Contract

Every actionable alert should aim to include these fields.

Identity:

```text
alertname
source_system
cluster
namespace
workload
pod
container
node
service
environment
```

Event context:

```text
event_name
event_reason
event_source
event_context
status
starts_at
severity
runbook_id
```

Routing:

```text
route_domain
target_agent
owner_team
automation_allowed
incident_candidate
```

Agent hints:

```text
summary
description
runbook_url
dashboard_url
suggested_log_query
suggested_kubectl
suggested_promql
recent_change_hint
```

## Where The Event Data Can Come From

Use labels when the field should drive routing, grouping, dedupe, ownership, or
agent selection.

Use annotations when the field is explanatory text or an investigation hint.

Possible sources:

```text
Prometheus series labels
  Good for cluster, namespace, pod, container, node, job, service.

Grafana/Prometheus alert rule labels
  Good for event_name, event_reason, route_domain, target_agent, severity,
  owner_team, runbook_id.

Grafana/Prometheus alert annotations
  Good for summary, description, suggested commands, log queries, dashboard
  links, and runbook links.

Vector enrichment
  Good for cluster/source mapping, owner lookup, target agent mapping, dedupe
  key creation, default routing, and quarantine decisions.

Kubernetes event exporter, Loki, Alloy, or another event/log source
  Required when the triage agent needs real Kubernetes event fields such as
  FailedScheduling, BackOff, Unhealthy, Killing, Pulled, FailedMount, or exact
  event messages.
```

## Important Constraint

If the work requirement is "send the Kubernetes event that caused this", a pure
metric alert is usually not enough. Metrics can indicate symptoms such as
restarts, unavailable endpoints, scheduling failures, or high latency, but the
exact Kubernetes event reason/message must come from a source that captures
Kubernetes events or logs.

Two valid patterns:

```text
Metric alert plus enriched hints:
Grafana alert rule -> labels/annotations -> Vector -> Kafka -> agent

True Kubernetes event route:
Kubernetes event exporter / Alloy / Loki -> Vector -> Kafka -> agent
```

The work agent should prove which pattern is being used for each scenario.

## Vector Normalized Envelope

Vector should emit one normalized actionable record per alert instance:

```json
{
  "source_system": "grafana",
  "source_receiver": "{{GRAFANA_CONTACT_POINT_NAME_OR_UID}}",
  "alert_name": "{{alerts[].labels.alertname}}",
  "event_name": "{{alerts[].labels.event_name}}",
  "event_reason": "{{alerts[].labels.event_reason}}",
  "event_source": "{{alerts[].labels.event_source}}",
  "cluster": "{{alerts[].labels.cluster}}",
  "namespace": "{{alerts[].labels.namespace}}",
  "pod": "{{alerts[].labels.pod}}",
  "container": "{{alerts[].labels.container}}",
  "service": "{{alerts[].labels.service}}",
  "severity": "{{alerts[].labels.severity}}",
  "status": "{{alerts[].status}}",
  "summary": "{{alerts[].annotations.summary}}",
  "description": "{{alerts[].annotations.description}}",
  "event_context": "{{alerts[].annotations.event_context}}",
  "suggested_log_query": "{{alerts[].annotations.suggested_log_query}}",
  "suggested_kubectl": "{{alerts[].annotations.suggested_kubectl}}",
  "runbook_url": "{{alerts[].annotations.runbook_url}}",
  "dashboard_url": "{{alerts[].annotations.dashboard_url}}",
  "route_domain": "{{alerts[].labels.route_domain}}",
  "target_agent": "{{alerts[].labels.target_agent}}",
  "dedupe_key": "{{cluster}}/{{namespace}}/{{pod}}/{{alert_name}}/{{event_reason}}",
  "normalization_gaps": []
}
```

Vector must read from `alerts[].labels` and `alerts[].annotations` first. Use
`commonLabels` and `commonAnnotations` only as fallbacks because grouped
notifications can omit fields that differ between alert instances.

## How To Put Context On The Alert

Grafana labels and annotations are templated per alert instance. Use template
variables so each firing instance carries its own resource identity, not a
static string.

Label templates (drive routing, grouping, dedupe, agent selection):

```text
event_name     = CoreDNSAvailabilitySignal          (static per rule)
event_reason   = EndpointHealthCheckFiring          (static per rule)
event_source   = grafana_alert_rule                 (static per rule)
route_domain   = {{ROUTE_DOMAIN}}                    (static per rule)
target_agent   = {{TARGET_AGENT}}                    (static per rule)
severity       = warning                             (static per rule)
runbook_id     = {{RUNBOOK_ID}}                       (static per rule)
```

Annotation templates (explanatory text and investigation hints, interpolated):

```text
summary            = {{ $labels.service }} on {{ $labels.cluster }} is firing
description        = Event {{ $labels.event_name }} on {{ $labels.namespace }}/{{ $labels.pod }} needs triage.
event_context      = event_name={{ $labels.event_name }}; resource={{ $labels.namespace }}/{{ $labels.pod }}; cluster={{ $labels.cluster }}
suggested_kubectl  = kubectl -n {{ $labels.namespace }} describe pod {{ $labels.pod }}
suggested_log_query= {namespace="{{ $labels.namespace }}", pod="{{ $labels.pod }}"}
```

Key rule: fields that must differ per instance (`pod`, `namespace`) must come
from the alert query result labels, then be referenced via `$labels.<name>` in
annotations. A static annotation string cannot become per-pod after the fact.

## Concrete Provisioning Example (API Fallback)

Prefer Grafana MCP. If MCP rule creation is unavailable, provision a
Grafana-managed rule with labels and annotations via the provisioning API. Keep
it clearly named and temporary.

```bash
curl -u admin:{{GRAFANA_PASSWORD}} \
  -X POST {{GRAFANA_URL}}/api/v1/provisioning/alert-rules \
  -H 'Content-Type: application/json' \
  -d '{
    "uid": "rich-context-proof",
    "title": "rich-context-proof",
    "condition": "A",
    "labels": {
      "event_name": "CoreDNSAvailabilitySignal",
      "event_reason": "EndpointHealthCheckFiring",
      "event_source": "grafana_alert_rule",
      "route_domain": "{{ROUTE_DOMAIN}}",
      "target_agent": "{{TARGET_AGENT}}",
      "severity": "warning",
      "runbook_id": "{{RUNBOOK_ID}}"
    },
    "annotations": {
      "summary": "{{ $labels.service }} on {{ $labels.cluster }} is firing",
      "description": "Event {{ $labels.event_name }} on {{ $labels.namespace }}/{{ $labels.pod }} needs triage.",
      "event_context": "event_name={{ $labels.event_name }}; resource={{ $labels.namespace }}/{{ $labels.pod }}; cluster={{ $labels.cluster }}",
      "suggested_kubectl": "kubectl -n {{ $labels.namespace }} describe pod {{ $labels.pod }}"
    }
  }'
```

The `data`/query block is omitted here; reuse the datasource UID and PromQL from
`GRAFANA-WEBHOOK-PAYLOAD-PROOF-README.md`, changing the target to
`{{TARGET_NAMESPACE}}`/`{{TARGET_WORKLOAD}}`. The query must return `cluster`,
`namespace`, and `pod` labels or the annotation templates render empty.

## Per-Instance Fan-Out (Implementation Note)

The contract says "one normalized record per alert instance". The bundled
home-lab VRL in `payload/observability-vector/homelab/vector-http-receiver-to-kafka.yaml`
currently reads `alerts[0]` only, so a grouped notification with two pods would
produce one record, not two. When proving rich context at work, confirm Vector
iterates `.alerts[]` rather than reading the first element.

Reference VRL shape for per-instance fan-out:

```text
# emit one event per alert instance
for_each(array!(.alerts)) -> |_index, alert| {
  record = {
    "source_system": "grafana",
    "alert_name": to_string(alert.labels.alertname) ?? "GrafanaAlert",
    "event_name": to_string(alert.labels.event_name) ?? "",
    "event_reason": to_string(alert.labels.event_reason) ?? "",
    "cluster": to_string(alert.labels.cluster) ?? to_string(.commonLabels.cluster) ?? "unknown",
    "namespace": to_string(alert.labels.namespace) ?? to_string(.commonLabels.namespace) ?? "unknown",
    "pod": to_string(alert.labels.pod) ?? "",
    "severity": to_string(alert.labels.severity) ?? "warning",
    "status": to_string(alert.status) ?? "firing",
    "description": to_string(alert.annotations.description) ?? "",
    "event_context": to_string(alert.annotations.event_context) ?? "",
    "suggested_kubectl": to_string(alert.annotations.suggested_kubectl) ?? "",
    "route_domain": to_string(alert.labels.route_domain) ?? "fallback",
    "target_agent": to_string(alert.labels.target_agent) ?? "sre-triage-agent"
  }
}
```

Read `alerts[].labels` and `alerts[].annotations` first; use `commonLabels`/
`commonAnnotations` only as fallbacks, because grouped notifications omit fields
that differ between instances (see `GRAFANA-WEBHOOK-PAYLOAD-PROOF-README.md`).

## Capture And Verify Commands

Use a temporary capture beside Vector to inspect the raw payload, then confirm
the normalized record on Kafka.

```bash
# 1. Raw webhook capture (temporary receiver beside Vector)
kubectl --context {{KUBE_CONTEXT}} -n {{TARGET_NAMESPACE}} \
  logs deploy/webhook-capture --tail=200 | jq '.alerts[0].labels, .alerts[0].annotations'

# 2. Confirm per-instance context exists in the raw payload
#    Expect one entry per firing pod, each with its own pod label.
kubectl --context {{KUBE_CONTEXT}} -n {{TARGET_NAMESPACE}} \
  logs deploy/webhook-capture --tail=200 | jq '.alerts | length, [.alerts[].labels.pod]'

# 3. Confirm the normalized record on the actionable Kafka topic
kafka-console-consumer --bootstrap-server {{KAFKA_BOOTSTRAP}} \
  --topic {{KAFKA_ACTIONABLE_TOPIC}} --from-beginning --max-messages 5 \
  | jq '{alert_name, event_name, event_reason, cluster, namespace, pod, route_domain, target_agent, normalization_gaps}'
```

If Vector logs to a debug/console sink instead of a capture pod, read the Vector
pod logs and grep for the alert name instead of steps 1-2.

## normalization_gaps Contract

Vector should never silently drop a should-have/nice-to-have field. When a
field is missing, append its name to `normalization_gaps` so the agent and
dashboards can see the gap.

```json
{
  "alert_name": "rich-context-proof",
  "cluster": "kind-argo-workflow",
  "namespace": "kube-system",
  "pod": "coredns-7d764666f9-bslbk",
  "event_name": "CoreDNSAvailabilitySignal",
  "event_reason": "",
  "suggested_kubectl": "",
  "normalization_gaps": ["event_reason", "suggested_kubectl"]
}
```

Rules:

- Missing must-have field -> route to quarantine, do not send to the actionable
  topic (see `KAFKA-TOPIC-DESIGN-README.md`).
- Missing should-have/nice-to-have -> send to actionable topic, list in
  `normalization_gaps`.
- Empty `normalization_gaps` is the success signal for a rich record.

## Cleanup

Remove every temporary object after the proof. Leaving a rule firing pollutes
work dashboards and can page a real team.

```bash
curl -u admin:{{GRAFANA_PASSWORD}} \
  -X DELETE {{GRAFANA_URL}}/api/v1/provisioning/alert-rules/rich-context-proof

kubectl --context {{KUBE_CONTEXT}} -n {{TARGET_NAMESPACE}} \
  delete deploy/webhook-capture --ignore-not-found

# Remove any chaos workload created only for this proof, and confirm no
# rich-context-proof alert is still in firing state in Grafana before finishing.
```

## Running This At Work

What changes versus the home lab:

- Fire against `{{TARGET_NAMESPACE}}`/`{{TARGET_WORKLOAD}}`, not `kube-system`.
  Pick a low-noise namespace so the proof does not compete with real alerts.
- Use the existing Manager/Grafana contact point into Vector; do not add a new
  contact point unless preflight shows none exists.
- Confirm least-privilege: the Grafana API user and Kafka credentials should be
  scoped to test operations only.
- Confirm Vector iterates `.alerts[]` (per-instance fan-out) before trusting the
  record count.
- Keep the rule name (`rich-context-proof`) obvious and temporary so operators
  can identify and delete it.
- If a true Kubernetes event reason/message is required and the metric alert
  cannot supply it, record the gap and point at the event-source pattern in the
  "Important Constraint" section rather than faking the field.

## Work-Agent Replication Prompt

Give this prompt to the work agent:

```text
You are validating the rich alert context contract for the Grafana/Alertmanager
-> Vector -> Kafka -> Argo -> agent flow.

Goal:
Prove that a real Grafana-managed alert rule, delivered through the existing
Grafana/Alertmanager webhook contact point into Vector, carries enough context
for the triage agent to investigate without relying on a generic alert name.

Use the existing working flow where possible:
Grafana/Alertmanager -> Vector webhook receiver -> Kafka actionable topic ->
Argo Sensor -> Argo Workflow -> triage agent.

Do not use synthetic curl payloads as the primary proof. You may use a temporary
webhook capture beside Vector only to inspect the raw Grafana/Alertmanager
payload before Vector transforms it.

Steps:
1. Confirm the active Grafana datasource, alert rule API/MCP access, contact
   point, Vector receiver URL, Kafka topic, Argo EventSource, Argo Sensor, and
   triage workflow.
2. Create a temporary or clearly named Grafana-managed alert rule that returns
   labels for cluster, namespace, pod, job/service, and any available workload
   identity.
3. Add alert rule labels for event_name, event_reason, event_source,
   route_domain, target_agent, severity, owner_team where known, and runbook_id.
4. Add alert annotations for summary, description, event_context,
   suggested_log_query, suggested_kubectl, runbook_url, and dashboard_url.
5. Fire the alert through the real contact point into Vector.
6. Capture the raw webhook payload before normalization if possible.
7. Verify the raw payload contains rich context under alerts[].labels and
   alerts[].annotations.
8. Verify Vector emits one normalized record per alert instance to Kafka.
9. Verify the Kafka record preserves event_name, event_reason, cluster,
   namespace, pod, description, suggested investigation hints, route_domain, and
   target_agent.
10. Verify Argo consumes the normalized record and the triage agent receives the
    full envelope.
11. If a true Kubernetes event reason/message is required, prove whether it is
    available from the metric alert. If it is not, document the required event
    source, such as Kubernetes event exporter, Alloy, or Loki.
12. Clean up the temporary alert rule, contact point route, capture endpoint,
    chaos workload, and any left-firing alert.

Evidence required:
GRAFANA_ALERT_RULE_UID:
GRAFANA_CONTACT_POINT:
RAW_WEBHOOK_CAPTURE: captured
RAW_ALERT_LABELS_EVENT_NAME: present
RAW_ALERT_LABELS_EVENT_REASON: present
RAW_ALERT_LABELS_CLUSTER: present
RAW_ALERT_LABELS_NAMESPACE: present
RAW_ALERT_LABELS_POD: present
RAW_ALERT_ANNOTATIONS_DESCRIPTION: present
RAW_ALERT_ANNOTATIONS_EVENT_CONTEXT: present
RAW_ALERT_ANNOTATIONS_SUGGESTED_KUBECTL: present
VECTOR_NORMALIZED_EVENT_NAME: present
VECTOR_NORMALIZED_EVENT_REASON: present
VECTOR_NORMALIZED_RESOURCE_CONTEXT: present
KAFKA_NORMALIZED_EVENT: consumed
ARGO_SENSOR_TRIGGER: verified
TRIAGE_AGENT_RECEIVED_FULL_CONTEXT: verified
TRUE_KUBERNETES_EVENT_SOURCE: verified_or_gap_recorded
CLEANUP: completed

Acceptance:
The work is complete only when the triage agent sees a rich normalized envelope,
not just an alert name. If fields are missing, identify whether the gap is in
the alert query, alert labels, alert annotations, Vector parsing, Kafka
normalization, or Argo workflow input mapping.
```

## References

Bundle siblings:

- `GRAFANA-WEBHOOK-PAYLOAD-PROOF-README.md` — raw payload shape, `alerts[]` vs
  `commonLabels` parsing rule, PromQL that returns resource labels.
- `KAFKA-TOPIC-DESIGN-README.md` — actionable/quarantine topic contract and when
  `normalization_gaps`/quarantine routing applies.
- `TWO-CLUSTER-CHAOS-README.md` — management vs events cluster split when Grafana
  and Vector live in different clusters.
- `prompts/01-preflight-env-tools.md` and `PREREQS-CHECKLIST.md` — discover the
  portable parameters before firing.

External docs:

- Grafana webhook contact points:
  `https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/`
- Grafana annotation and label templates:
  `https://grafana.com/docs/grafana/latest/alerting/alerting-rules/templates/`
- Grafana notification templates and payload behavior:
  `https://grafana.com/docs/grafana/latest/alerting/configure-notifications/template-notifications/`
