# Dual-Source Kafka Routing for kagent Triage

## Decision

Run two **non-overlapping** signal lanes into kagent triage:

| Lane | Authoritative producer | Allowed signal class | Do not use it for |
|---|---|---|---|
| Metric lane | Alertmanager, via its existing webhook or Kafka bridge | Prometheus/Grafana **metric** alerts only | Kubernetes events, application logs, or LogQL-derived alerts |
| Evidence lane | Alloy -> Vector -> Kafka | Kubernetes events and allow-listed application/platform logs | CPU, memory, availability, latency, or other metric-rule alerts |

The evidence lane is the authoritative path for event and log context. It
bypasses Alertmanager so the triage request retains the event reason and a
bounded, redacted evidence package. Alertmanager remains useful for
metric-based detection, where it is the authoritative grouped alert source.

This is a routing policy, not an assertion that either source is currently
healthy in Confluent Cloud. The repository contains a Confluent proof of
concept and public-safe placeholders; an operator must verify the current
cluster, topics, service accounts, ACLs, and offsets before rollout.

```text
metric lane
  metric rule -> Alertmanager -> metric-alerts input topic --+
                                                          |
evidence lane                                             v
  logs + K8s events -> Alloy -> Vector -> evidence input topic
                                            |
                                            +-> triage ingress/router
                                                  | validates source ownership
                                                  | claims durable incident key
                                                  v
                                      incident-triage-requests
                                                  |
                                             Argo -> read-only kagent
                                                  |
                                      incident-triage-results / DLQ
```

## Why the split is necessary

Alertmanager deliberately reduces an alert to a grouped notification. That is
the right behavior for metric alerts, but it is not a reliable evidence
transport for logs and Kubernetes events: it can lose the original event
reason, ordering, repetition pattern, and representative log context. The
direct Vector route can normalize, correlate, redact, and bound that context
before it becomes agent work.

Neither lane is inherently a replacement for the other:

- Alertmanager detects the metric conditions it has rules for.
- Alloy/Vector supplies direct event/log evidence and event-driven detection.
- Loki/Grafana remain the retained search and human-investigation surface; they
  are not a third automation trigger in this design.

## Proposed cluster-health state lane

Status: design proposal from the reviewed [cluster-health assessment plan](../../work-agent-bundles/cluster-health-assessment-plan/README.md). This section does not change the existing two incident-producing lanes or authorise a deployed route.

The state lane carries bounded, interval-based cluster snapshots on separately mapped topics. It does not send per-finding monitor records into the metric/evidence ingress or create workload-incident tickets. Its optional writer owns one labelled cluster-health summary per cluster and environment.

Metric and evidence lanes retain incident ownership. The health summary links confirmed incident IDs from a bounded central results/mapping lookup, adds aggregate impact and coverage, and avoids duplicating their remediation work items. If no match exists, mark the link unavailable rather than inventing one or creating a workload ticket.

With both paths deliberately enabled, one crash-looping workload may create one existing incident issue and one cluster summary linking it. The coexistence acceptance count is at most two, not one total. If one ticket total is required, keep the state lane report-only or explicitly disable the other writer for the approved pilot scope.

State-lane budgets do not contain an uncontrolled existing writer. Require the original path's own dedupe and creation limits before enabling coexistence. Inventory every consumer of the monitor's current topic, especially any that trusts `ai_triage_required`. The revised snapshot adapter strips that flag and has no direct path to the old Sensors.

Source identity, namespace allowlists, catch-up coalescing, and snapshot completeness follow the [proposed architecture](../../work-agent-bundles/cluster-health-assessment-plan/ARCHITECTURE.md). Retain the current metric/evidence payload contracts and consumer groups until a separately reviewed migration changes them.

## Kafka topology

Use topics by message contract, not by namespace, application, or agent. The
names below are a target naming convention; map them to the existing Confluent
names during migration rather than creating duplicate parallel paths.

| Topic | Producers | Consumers | Retention intent |
|---|---|---|---|
| `kagent.triage.metric-alerts.v1` | Alertmanager bridge/webhook normalizer | triage ingress/router | Short replay window for metric input |
| `kagent.triage.evidence.v1` | Vector only | triage ingress/router | Short replay window for normalized event/log evidence |
| `kagent.triage.requests.v1` | triage ingress/router | Argo EventSource | Sufficient to replay work safely after an Argo outage |
| `kagent.triage.results.v1` | triage workflow/result publisher | audit, reporting, incident views | Longer audit/operational retention |
| `kagent.triage.dlq.v1` | ingress/router and workflow error paths | controlled replay/remediation process | Long enough for human review |

Raw telemetry is not a triage topic. If raw Kafka retention is needed for a
specific replay/audit case, keep it in a separately access-controlled topic
with an explicit data classification and retention decision.

The current proof-of-concept topics `k8s-events` and `alertmanager-events`
remain separate because their payloads differ. They should feed the target
contracts above through a normalizer; do not point both directly at the same
Argo Sensor and expect it to infer the schema.

### Partition key

All producers must set a key. Use a stable workload/incident affinity key:

```text
cluster | environment | namespace | workload-or-service
```

This preserves useful ordering for a workload while allowing separate
workloads to scale across partitions. Do not key on a timestamp, pod UID alone,
or a random UUID; those defeat ordering and make duplicate suppression harder.
Choose partition count from expected peak throughput and recovery time, then
increase it only with a deliberate key-ordering review. It is not a namespace
count.

## Consumer-group model

A consumer group distributes partitions among its members. It does **not**
deduplicate two records just because they describe the same incident, and two
different consumer groups each receive their own copy. The group design is:

| Group | Subscription | Purpose | Scale rule |
|---|---|---|---|
| `kagent-triage-ingress-v1` | metric and evidence input topics | Validate source ownership, normalize to one incident contract, claim idempotency, publish requests | Members may scale to no more than the assigned partitions |
| `kagent-triage-argo-v1` | `kagent.triage.requests.v1` | Argo EventSource submits triage workflows | One logical production group; do not run a second active EventSource with the same job under a new group |
| `kagent-triage-audit-v1` | requests and results | Reporting/audit only | Independent by design; it must never submit workflows |
| `kagent-triage-replay-v1` | DLQ only | Human-approved repair and replay | Disabled except during controlled replay |

The ingress router is the key boundary. It may be a small service, a managed
stream processor, or an existing Vector-capable normalization component, but
it must make a durable idempotency decision before publishing a triage request.
Argo Events alone should not be treated as that cross-topic dedupe store.

Commit an input offset only after the router has either:

1. written/updated the durable incident claim and published the request through
   a transactional outbox or equivalent reliable handoff; or
2. recorded the message in the DLQ with its failure reason.

This makes at-least-once delivery safe. Do not claim end-to-end exactly-once
workflow execution: Kafka retry, EventSource restart, and workflow submission
can all repeat. The triage workflow and ticket/incident writer must therefore
also be idempotent on `incident_id`.

## Source-ownership contract

Every input must carry these explicit fields before it can enter the router:

```json
{
  "schema_version": "observability.triage.input.v1",
  "producer": "alertmanager | vector",
  "signal_class": "metric | kubernetes-event | log",
  "source_record_id": "{{PRODUCER_STABLE_ID}}",
  "cluster": "{{CLUSTER_NAME}}",
  "environment": "{{ENVIRONMENT}}",
  "observed_at": "{{RFC3339_TIMESTAMP}}"
}
```

Enforce this allow-list at ingress:

| Producer | Accepted `signal_class` | Required routing guard |
|---|---|---|
| `alertmanager` | `metric` | Alert rule carries `triage_signal=metric`; metric rule name/fingerprint is present |
| `vector` | `kubernetes-event`, `log` | Original event type/reason or log signature is present; evidence is redacted and bounded |

Route an Alertmanager record labelled as a log/event, or a Vector record marked
as a metric, to the DLQ with `reason=source-ownership-violation`. Do not
silently reinterpret it. This is the primary prevention against overlapping
automation paths.

For Alertmanager, add an explicit receiver route that selects only
`triage_signal=metric`. Remove that label from rules derived from logs/events,
or send those to a human-notification receiver that cannot create triage work.
For Vector, use an allow-list of event reasons and error signatures; routine
logs and all metric samples stay out of the evidence topic.

## Duplicates: prevention, then durable idempotency

### 1. Prevent intended duplicates

The policy above means the same source class has one owner:

- `CrashLoopBackOff`, `FailedScheduling`, `ImagePullBackOff`, and matching
  error logs: Vector evidence lane.
- CPU saturation, memory working set, latency, error-rate, availability, and
  other Prometheus metric-rule conditions: Alertmanager metric lane.

Metric alerts that happen to coincide with an evidence incident are not proof
of duplicate delivery. They may be separate symptoms of the same outage. The
router must decide whether to attach the metric signal to an open incident or
open a new incident according to a documented correlation policy.

### 2. Suppress delivery repeats

First remove transport duplicates using `source_record_id`; for Kafka sourced
messages record topic, partition, and offset as transport provenance. This
only protects a repeated delivery of the same source record.

### 3. Claim the logical incident across both lanes

Compute a source-independent `incident_key`, for example:

```text
v1 | cluster | environment | namespace | workload/service |
   symptom-family | normalized-reason-or-alert-family | time-window
```

`symptom-family` is deliberately coarser than a raw alert name. Examples:
`workload-crash`, `scheduling`, `image-pull`, `resource-saturation`, and
`availability`. The router persists a claim keyed by this value with an owner,
creation time, last-seen time, route, and the emitted `incident_id`.

When a message arrives:

1. Look up and atomically claim `incident_key`.
2. If no active claim exists, emit one `incident-triage-request` and store its
   `incident_id`.
3. If an active claim exists, append bounded evidence/metric context to the
   same incident and publish an update only when policy permits; do not create
   another workflow or ticket.
4. Extend the TTL while the symptom remains active; close the claim on a
   resolved event/alert where available, otherwise let a documented inactivity
   TTL expire.

The claim store must be durable and shared by all ingress replicas. A
ConfigMap, in-memory cache, or consumer-group assignment is insufficient.
Use an approved datastore with atomic conditional create/update and an expiry
policy. Keep the incident claim free of raw log lines or secrets.

### 4. Make downstream side effects idempotent

Pass `incident_id` to Argo as the workflow/ticket correlation key. Before
creating a workflow, ticket, Teams notification, or remediation request, check
whether that side effect was already created for the same incident and action
version. Retries should resume or update, not fan out again.

## Normalized request contract

Both lanes become this one bounded request after the router, never before:

```json
{
  "schema_version": "observability.triage.v2",
  "incident_id": "{{STABLE_INCIDENT_ID}}",
  "incident_key": "{{SOURCE_INDEPENDENT_KEY}}",
  "source_types": ["metric"],
  "cluster": "{{CLUSTER_NAME}}",
  "environment": "{{ENVIRONMENT}}",
  "namespace": "{{NAMESPACE}}",
  "service": "{{SERVICE_NAME}}",
  "severity": "critical",
  "symptom_family": "resource-saturation",
  "reason": "HighCpuUsage",
  "observed_at": "{{RFC3339_TIMESTAMP}}",
  "evidence": {
    "metric_summary": "CPU usage exceeded the agreed threshold",
    "event_summary": null,
    "log_signature": null,
    "representative_log_lines": []
  },
  "route_key": "{{ROUTE_KEY}}",
  "dedupe_key": "{{INCIDENT_KEY}}",
  "automation_allowed": false
}
```

For a Vector-originated request, `source_types` contains `kubernetes-event`
and/or `log`, and `event_summary`, `reason`, and a small number of redacted log
lines may be populated. For a metric request, event/log fields remain empty;
the agent can use links and follow-up read-only tools, but the router must not
invent event reasons.

## Confluent Cloud setup requirements

Provision through the organisation's approved Confluent Terraform/IaC or
Confluent administration process. Do not place credentials in Git.

1. Confirm the existing Confluent environment and Kafka cluster are the
   approved shared bus. Record only its public-safe alias in this repository.
2. Create or map the five contract topics above, with explicit retention,
   partition count, cleanup policy, and owner. Create the DLQ before enabling
   either producer.
3. Create separate service accounts and least-privilege ACLs:
   - Alertmanager publisher: write to metric input only.
   - Vector publisher: write to evidence input only.
   - ingress router: read both inputs; write requests, results when applicable,
     and DLQ.
   - Argo EventSource: read requests only.
   - audit/replay: read only the topics required by their function.
4. Define Schema Registry compatibility and validate both input schemas and
   the normalized request schema. Do not enable broker-side schema validation
   for a producer until its serializer/wire format is proven compatible.
5. Create the named consumer groups, start at the intended offsets, and alert
   on consumer lag, rebalance frequency, DLQ volume, source-ownership
   violations, and duplicate-claim suppression.
6. Store Confluent endpoints and credential references in the approved secret
   store/Kubernetes secrets. The repository must retain `{{PLACEHOLDER}}`
   values only.

## Rollout and proof

Start with a narrow parallel pilot; leave existing Alertmanager behavior
unchanged until the evidence lane is proven.

1. **Inventory:** list current Alertmanager rules and classify each as metric,
   event/log-derived, or unknown. Unknown rules do not enter triage.
2. **Configure source ownership:** route only the metric allow-list from
   Alertmanager; deploy the Vector allow-list for Warning events and error
   signatures.
3. **Prove each lane independently:** inject one CPU/latency metric condition
   and one controlled failing workload that emits an event plus matching logs.
4. **Prove collision handling:** create a workload failure that also causes a
   metric alert. The result must be one incident/workflow, with the second
   signal attached as context rather than a second triage invocation.
5. **Prove retries:** replay the same Kafka record and restart the ingress and
   Argo consumers. The incident, workflow, ticket, and notification counts
   must remain one.
6. **Observe:** capture producer success, input/request topic offsets and lag,
   claim-store decision, DLQ count, EventSource delivery, workflow completion,
   and the agent's received evidence package.

The safe initial outcome is read-only triage. Remediation remains a separate,
human-approved GitOps/workflow action path.

## Related repository material

- [Alloy -> Vector -> Kafka agent-triage plan](alloy-vector-kafka-agent-triage-plan.md)
  defines the evidence-first data contract and pilot sequence.
- [Catent Alertmanager to Confluent routing](catent-alertmanager-confluent-routing.md)
  contains the existing Alertmanager/Vector normalization and agent-routing
  guidance.
- [Confluent Cloud pipeline PoC](../../observability/confluent-cloud-pipeline/README.md)
  documents the current public-safe `k8s-events` and `alertmanager-events`
  proof shape.
- [Sensor safeguards](../../agents/kagent-triage/SENSOR-SAFEGUARDS.md)
  provides mandatory rate limiting and loop prevention for Argo Sensors.
