# Prompt 08: Prove Rich Alert Context

Use this after the base Grafana/Alertmanager -> Vector -> Kafka -> Argo path is
working.

## Objective

Prove that real Grafana/Alertmanager alerts deliver enough context for the
triage agent to isolate and investigate the issue quickly. The agent should not
receive only a generic alert name.

## Required Flow

```text
Grafana-managed alert rule / Alertmanager
  -> existing Vector webhook receiver
  -> Vector normalization and routing
  -> Kafka actionable topic
  -> Argo Sensor
  -> Argo Workflow
  -> triage agent
```

## Portable Parameters

This prompt was proved in a home lab against `kind-argo-workflow` / `kube-system`
/ `coredns`. Do not copy those literally. Map the parameter table in
`RICH-ALERT-CONTEXT-README.md` ("Portable Parameters") to the work environment
first, using `prompts/01-preflight-env-tools.md` and `PREREQS-CHECKLIST.md`.

Fire against a low-noise `{{TARGET_NAMESPACE}}` / `{{TARGET_WORKLOAD}}`, reuse
the existing Manager/Grafana contact point into Vector, and use least-privilege
Grafana and Kafka credentials. Name the temporary rule `rich-context-proof` so
it is easy to find and delete.

## Instructions

1. Read `RICH-ALERT-CONTEXT-README.md`, including "How To Put Context On The
   Alert", "Per-Instance Fan-Out", and "normalization_gaps Contract".
2. Confirm the existing Grafana datasource, contact point, Vector receiver,
   Kafka topic, Argo EventSource, Argo Sensor, and triage workflow.
3. Create a temporary Grafana-managed alert rule through Grafana MCP or the
   Grafana API fallback.
4. The alert query must return resource labels such as `cluster`, `namespace`,
   `pod`, and `service` where available.
5. Add explicit alert labels:

```text
event_name
event_reason
event_source
route_domain
target_agent
severity
owner_team
runbook_id
```

6. Add explicit annotations. Use `{{ $labels.<name> }}` templating so per-instance
   fields (`pod`, `namespace`) interpolate per firing instance, not as a static
   string:

```text
summary
description
event_context
suggested_log_query
suggested_kubectl
suggested_promql
runbook_url
dashboard_url
```

7. Fire the alert through the real contact point into Vector.
8. Capture the raw webhook payload before Vector normalization if possible.
9. Verify the raw webhook payload uses `alerts[].labels` and
   `alerts[].annotations` for per-alert context.
10. Verify Vector emits one normalized actionable Kafka record per alert
    instance. Confirm Vector iterates `.alerts[]` (per-instance fan-out) and does
    not read `alerts[0]` only. Fire a grouped notification with 2+ pods and
    confirm 2+ Kafka records. Confirm missing should-have fields are listed in
    `normalization_gaps`, not silently dropped.
11. Verify Argo and the triage agent receive the normalized envelope.
12. Record whether real Kubernetes event reason/message data is available from
    the alert source. If not, record the required event source integration.
13. Clean up every temporary rule, route, receiver, chaos workload, and
    left-firing alert.

## Evidence Markers

```text
RICH_CONTEXT_ALERT_RULE: created
RICH_CONTEXT_ALERT_FIRED: verified
RAW_ALERT_LABELS_EVENT_NAME: present
RAW_ALERT_LABELS_EVENT_REASON: present
RAW_ALERT_LABELS_RESOURCE: present
RAW_ALERT_ANNOTATIONS_EVENT_CONTEXT: present
VECTOR_RICH_CONTEXT_NORMALIZED: verified
VECTOR_PER_INSTANCE_FANOUT: verified
NORMALIZATION_GAPS_POPULATED: verified_or_empty
KAFKA_RICH_CONTEXT_CONSUMED: verified
ARGO_RICH_CONTEXT_TRIGGER: verified
TRIAGE_AGENT_RECEIVED_FULL_CONTEXT: verified
TRUE_KUBERNETES_EVENT_SOURCE: verified_or_gap_recorded
RICH_CONTEXT_CLEANUP: completed
```

## Stop Conditions

Stop and record a gap if:

- the alert query strips resource labels before notification delivery
- Vector reads only `commonLabels` and loses per-alert labels
- Vector reads `alerts[0]` only and collapses a multi-instance group to one record
- a must-have field (resource anchor, severity, status) is missing
- Kafka records contain the alert name but not the resource or event context
- Argo workflow input mapping drops the normalized envelope
- a true Kubernetes event is required but no event/log source is connected

## Related

- `RICH-ALERT-CONTEXT-README.md` — the full contract, provisioning example,
  VRL fan-out shape, capture/verify commands, and cleanup.
- `GRAFANA-WEBHOOK-PAYLOAD-PROOF-README.md` — raw payload parsing rule.
- `KAFKA-TOPIC-DESIGN-README.md` — actionable vs quarantine routing for gaps.
- `prompts/01-preflight-env-tools.md` — discover parameters first.
- `prompts/06-assess-existing-webhook-proxy-cleanup.md` — run if a
  webhook/proxy chain sits in front of Vector.
- `prompts/07-chaos-gameday-end-to-end.md` — prove rich context under chaos.
