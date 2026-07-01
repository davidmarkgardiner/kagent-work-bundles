# Vector and Confluent Event Management

This folder captures a public-safe design note for using
[Vector](https://github.com/vectordotdev/vector) to improve the existing
Confluent Cloud observability pipeline.

The current proof of concept is documented in
[`../confluent-cloud-pipeline/README.md`](../confluent-cloud-pipeline/README.md).
It already separates Kubernetes events and Alertmanager events into distinct
Confluent topics, then uses Argo Events to trigger Argo Workflows:

```text
Alloy / Alertmanager bridge
  -> Confluent Cloud topics
  -> Argo Events Kafka EventSource
  -> Argo Events Sensor
  -> Argo Workflow
```

## Recommendation

Use Vector as an optional event normalization and noise-reduction layer around
Confluent. Do not replace Argo Sensors in the first pass.

Vector is strongest at event transport, parsing, remapping, filtering, and
lightweight deduplication. Argo Sensors are still the right boundary for
creating Argo Workflows from accepted events.

Recommended first shape for alerts:

```text
Alertmanager
  -> Confluent raw topic: alertmanager-events
  -> Vector in the management cluster
  -> Confluent normalized topic: alertmanager-events-triage
  -> Argo Events Kafka EventSource
  -> Argo Sensor
  -> Argo Workflow
```

Vector acts as both a Kafka consumer and Kafka producer. It reads the raw
Alertmanager event from Confluent, sorts it out into a smaller automation-ready
shape, and writes that cleaned event back to a separate Confluent topic. Argo
then watches the cleaned topic rather than the raw topic.

The deployable spike manifests are in [`manifests/`](manifests/):

- [`01-vector-alertmanager-normalizer.yaml`](manifests/01-vector-alertmanager-normalizer.yaml)
  deploys Vector in the management cluster, consumes `alertmanager-events`,
  normalizes the payload, and publishes `alertmanager-events-triage`.
- [`02-argo-alertmanager-triage-topic.yaml`](manifests/02-argo-alertmanager-triage-topic.yaml)
  adds a second Argo Events Kafka EventSource and Sensor for the normalized
  topic.
- [`03-argo-routing-verification.yaml`](manifests/03-argo-routing-verification.yaml)
  adds a lightweight route-verification Sensor and WorkflowTemplate. It only
  triggers for synthetic records where `routing_test: "true"`.

For Kubernetes events the same pattern can be added later:

```text
Alloy
  -> Confluent raw topic: k8s-events
  -> Vector in the management cluster
  -> Confluent normalized topic: k8s-events-triage
  -> Argo Events Kafka EventSource
  -> Argo Sensor
  -> Argo Workflow
```

## Ingestion Design Decision

Alertmanager can send directly to Vector if Vector exposes an HTTP receiver.
That path is technically valid:

```text
Alertmanager
  -> Vector HTTP endpoint in the management cluster
  -> Vector normalize / filter / dedupe
  -> Confluent normalized topic: alertmanager-events-triage
  -> Argo Events Kafka EventSource
  -> Argo Sensor
  -> Argo Workflow
```

Do not make that the default platform design for this repo. Prefer Kafka first:

```text
Alertmanager
  -> Confluent raw topic: alertmanager-events
  -> Vector in the management cluster
  -> Confluent normalized topic: alertmanager-events-triage
  -> Argo Events Kafka EventSource
  -> Argo Sensor
  -> Argo Workflow
```

Kafka-first is the safer platform pattern because the raw alert is captured
before Vector touches it. That gives the team replay, auditability, easier
debugging, and looser coupling between Alertmanager delivery and Vector uptime.
If Vector is down, it can catch up from Kafka when it recovers. In a
direct-to-Vector path, Alertmanager delivery depends on Vector being reachable
and healthy at receive time.

Use direct-to-Vector only for a smaller or lower-criticality deployment where
the extra raw Kafka topic is not worth the operational cost.

Both patterns have now been verified in the home-lab management cluster:

| Pattern | Verified path | Auth boundary |
|---|---|---|
| Kafka-first | Alertmanager-style payload -> bridge -> `alertmanager-events` -> Vector -> `alertmanager-events-triage` -> Argo Workflow | Producer auth is handled before Vector; Vector needs Kafka consume on the raw topic and produce on the normalized topic. |
| Direct-to-Vector | Raw Alertmanager webhook -> Vector HTTP receiver -> `alertmanager-events-triage` -> Argo Workflow | Alertmanager needs network/auth to Vector HTTP; Vector needs Kafka produce on the normalized topic. |

The direct-to-Vector verification used the raw Alertmanager webhook shape at
the HTTP receiver, not a pre-wrapped internal test envelope.

## What Vector Adds

| Area | Current shape | Vector enhancement |
|---|---|---|
| Payload contracts | Alloy, Alertmanager, and Grafana-native Kafka payloads have different shapes. | Normalize each source into a common triage envelope before Argo sees it. |
| Filtering | Some filtering happens in Alloy, Sensor filters, or workflow code. | Move source-agnostic filtering into a visible event pipeline. |
| Deduplication | Current workflow-level dedupe uses a ConfigMap cache in Argo. | Suppress repeated events before they create workflows, using a `dedupe_key` contract. |
| Topic design | Raw source topics are routed directly to workflow triggers. | Keep raw topics for audit/replay and publish normalized topics for automation. |
| Workflow complexity | Workflows parse and classify incoming records. | Workflows receive a smaller, stable event shape. |

Worked examples for these areas are in [`examples/`](examples/). They show raw
Alertmanager, Grafana-native, and Alloy/Kubernetes payloads, plus expected
normalized envelopes and routing cases.

The examples can be tested with the actual Vector container:

```bash
observability/vector/tests/run-vector-example-tests.sh
```

That test uses
[`tests/vector-example-test.yaml`](tests/vector-example-test.yaml) to run:

```text
stdin fixture
  -> Vector remap normalization
  -> Vector filter
  -> Vector dedupe
  -> console output assertions
```

Current tested cases:

- Alertmanager payload contract and routing to `aks-sre-triage-agent`.
- Grafana-native payload contract and routing to `aks-sre-triage-agent`.
- Alloy/Kubernetes event contract and routing to `platform-ops-agent`.
- Resolved Alertmanager and Grafana alert filtering before workflow creation.
- Count-bounded duplicate suppression using a stable `dedupe_key`.

Use the examples as the acceptance test shape for the Vector layer:

| Area | Example evidence to produce | Acceptance criteria |
|---|---|---|
| Payload contracts | Feed [`examples/alertmanager-raw.json`](examples/alertmanager-raw.json), [`examples/grafana-native-raw.json`](examples/grafana-native-raw.json), and [`examples/alloy-k8s-event-raw.json`](examples/alloy-k8s-event-raw.json) through Vector. | Every source emits `schema_version: observability.triage.v1` with stable top-level `source`, `event_type`, `cluster`, `namespace`, `severity`, `service`, `target_agent`, `route_key`, and `dedupe_key` fields. |
| Filtering | Send resolved alerts, low-priority noisy namespaces, and critical production alerts. | Vector drops or down-routes noise before Argo creates a workflow; critical production alerts still publish to the normalized topic. |
| Deduplication | Send the same alert three times while the Vector dedupe cache still contains the key. | All copies calculate the same `dedupe_key`; only the first event reaches the normalized automation topic while the key remains in the cache. |
| Topic design | Produce raw events to `alertmanager-events`, `grafana-alerts`, or `k8s-events`. | Raw topics retain the original payload for audit/replay; normalized topics contain the smaller automation contract. |
| Workflow complexity | Compare Argo workflow parameters before and after Vector. | Argo reads routing and context fields directly rather than parsing source-specific payloads in shell/JQ workflow steps. |

## Proposed Triage Envelope

Vector should publish normalized records with a small, explicit contract:

```json
{
  "schema_version": "observability.triage.v1",
  "source": "alloy|alertmanager|grafana",
  "cluster": "{{CLUSTER_NAME}}",
  "environment": "{{ENVIRONMENT}}",
  "severity": "critical|warning|info",
  "event_type": "kubernetes-event|prometheus-alert|grafana-alert",
  "reason": "CrashLoopBackOff",
  "object_kind": "Pod",
  "namespace": "default",
  "name": "example-pod",
  "pod": "example-pod",
  "service": "example-service",
  "target_agent": "sre-triage-agent",
  "route_key": "alerts.default.example-service.warning.sre-triage-agent",
  "routing_reason": "warning pod event in application namespace",
  "incident_candidate": false,
  "automation_allowed": false,
  "dedupe_key": "{{CLUSTER_NAME}}:default:Pod:example:CrashLoopBackOff",
  "event_time": "2026-06-29T00:00:00Z",
  "raw_topic": "k8s-events",
  "normalized_topic": "k8s-events-triage",
  "raw": {}
}
```

The `raw` field should preserve the original payload for audit and debugging.
Downstream Argo Sensors should filter against the normalized top-level fields,
not nested source-specific payloads.

## Deduplication Position

Vector can reduce duplicate workflow submissions, but it should not be the only
durable dedupe layer for high-value incident handling.

Use Vector for:

- Count-bounded suppression of repeated noisy events.
- Contract-based dedupe keys before events reach Argo.
- Reducing duplicate Workflow objects and alert fatigue.

Keep workflow or downstream dedupe for:

- Durable 24-hour incident grouping.
- Human-in-the-loop remediation safety.
- Cases where a Vector restart should not reset incident memory.

The current Vector manifest uses the Vector `dedupe` transform with
`cache.num_events: 1000`. Treat that as a noise-reduction cache, not as a
durable incident database or a strict time-window guarantee.

## Argo Integration

Vector should not replace Argo Sensors initially.

Keep Argo Sensors because they provide the clear Kubernetes-native trigger
boundary:

- Kafka event accepted.
- Filter matched.
- Workflow object created.
- Rate limit and retry strategy applied.

Vector should replace the parsing and normalization work around the Sensor, not
the Sensor's job of submitting Workflows.

Target Argo change for the first alert spike:

```text
EventSource topic: alertmanager-events-triage
Sensor filters: body.schema_version, body.severity, body.event_type, body.source
Workflow parameter: normalized event payload
```

## Verified Spike Flows

The Kafka-first live spike was run against the management cluster using
sanitized test data:

```text
Synthetic Alertmanager payload
  -> alertmanager-confluent-bridge /alertmanager
  -> Confluent raw topic: alertmanager-events
  -> vector-alertmanager-normalizer
  -> Confluent normalized topic: alertmanager-events-triage
  -> vector-alertmanager-triage-kafka EventSource
  -> vector-alertmanager-triage Sensor
  -> alertmanager-triage WorkflowTemplate
```

Validation evidence from the run:

- The bridge accepted the synthetic Alertmanager webhook with HTTP `202`.
- Vector consumed the raw Kafka record and emitted a normalized record with
  `schema_version: observability.triage.v1`,
  `pipeline: vector-alertmanager-normalizer`, and a generated `dedupe_key`.
- The normalized-topic Argo EventSource consumed
  `alertmanager-events-triage` and published the event onto the Argo EventBus.
- The Vector Sensor created a workflow named `alert-triage-vector-*`.
- The workflow completed successfully.

The direct-to-Vector live spike was also run against the management cluster:

```text
Raw Alertmanager webhook payload
  -> vector-alert-webhook-normalizer /alerts
  -> Confluent normalized topic: alertmanager-events-triage
  -> vector-alertmanager-triage-kafka EventSource
  -> vector-alertmanager-triage Sensor
  -> alertmanager-triage WorkflowTemplate
```

Validation evidence from the direct run:

- Vector accepted the raw Alertmanager webhook with HTTP `200`.
- The normalized-topic Argo EventSource consumed the event from
  `alertmanager-events-triage`.
- The Vector Sensor created `alert-triage-vector-rpwvn`.
- The workflow payload contained the direct receiver marker and raw
  Alertmanager fields.
- The workflow completed successfully.

During the spike, the existing raw Alertmanager Sensor remained enabled. That
means one test alert created two workflows:

```text
alertmanager-events        -> existing raw Sensor       -> alert-triage-*
alertmanager-events-triage -> Vector-normalized Sensor  -> alert-triage-vector-*
```

This duplicate trigger is useful for comparison during testing, but should not
be the steady-state production design. Once the normalized path is accepted, the
raw Sensor should be disabled or narrowed to replay/debug use.

## Routing Plan

Vector should become the routing and normalization harness before Argo receives
an event. Argo should keep the reliable Kubernetes trigger boundary, but it
should stop doing source-specific parsing, lightweight dedupe, and agent
selection where possible.

Recommended routing contract:

```json
{
  "schema_version": "observability.triage.v1",
  "source": "alertmanager",
  "event_type": "prometheus-alert",
  "severity": "warning",
  "cluster": "{{CLUSTER_NAME}}",
  "namespace": "default",
  "service": "{{SERVICE_NAME}}",
  "target_agent": "sre-triage-agent",
  "route_key": "alerts.default.warning.sre-triage-agent",
  "dedupe_key": "{{CLUSTER_NAME}}:default:{{ALERT_NAME}}:warning",
  "alertmanager": {},
  "raw": {}
}
```

Start with one normalized topic:

```text
alertmanager-events
  -> Vector normalize / classify / assign target_agent
  -> alertmanager-events-triage
  -> one Argo Sensor
  -> one generic triage WorkflowTemplate
```

This keeps the first production rollout simple. Argo reads `target_agent` and
`route_key` from the normalized payload and passes them into the workflow. The
workflow can then call the correct kagent or agent service without maintaining
source-specific routing logic.

After that is stable, consider topic-level routing:

```text
alertmanager-events
  -> Vector
     -> alerts-platform-triage
     -> alerts-security-triage
     -> alerts-networking-triage
     -> alerts-application-triage
```

Topic-level routing is useful when teams need independent scaling, ownership,
retention, replay, or Sensor policies. It is heavier than a single normalized
topic because every new route needs topic management, ACLs, EventSources,
Sensors, and workflow policy.

Suggested route fields:

| Field | Owner | Purpose |
|---|---|---|
| `target_agent` | Vector | Selects the kagent or agent service to call. |
| `route_key` | Vector | Stable routing label for metrics, dashboards, and audits. |
| `routing_reason` | Vector | Explains why this agent/topic was selected. |
| `dedupe_key` | Vector | Duplicate suppression key for the Vector cache and downstream grouping. |
| `incident_candidate` | Vector | Indicates whether the event is likely to need ServiceNow/GitLab escalation. |
| `automation_allowed` | Vector | Default-deny hint. Write-capable remediation still requires an explicit Argo-side allowlist and service account gate. |

Route using the most stable ownership signal available:

| Signal | Why it matters | Example route |
|---|---|---|
| `namespace` | Usually maps to platform area, environment, or application ownership. | `kube-system` -> `platform-ops-agent`; `payments` -> `application-triage-agent`. |
| `service` | More stable than pod names and better for incident grouping. | `checkout-api` -> application service triage. |
| `pod` | Needed for diagnostics, logs, events, and pod-specific remediation. | `checkout-api-...` -> fetch pod logs/events before agent handoff. |
| `alert_name` or `reason` | Maps known conditions to specialist playbooks. | `ImageVulnerability` -> `security-hardening-agent`; `FailedScheduling` -> `platform-ops-agent`. |
| `severity` | Controls urgency, automation depth, and escalation. | `critical` in `prod` -> incident candidate; `warning` in `dev` -> triage only. |
| `cluster` and `environment` | Separates dev, prod, and management cluster behavior. | Production alerts can use stricter workflows and approval gates. |

Examples:

- [`examples/normalized-platform-alert.json`](examples/normalized-platform-alert.json)
  routes a critical production pod alert to `aks-sre-triage-agent`.
- [`examples/normalized-security-alert.json`](examples/normalized-security-alert.json)
  routes a vulnerability/compliance event to `security-hardening-agent` with
  `automation_allowed: false`.
- [`examples/routing-cases.json`](examples/routing-cases.json) captures the
  first set of routing cases to encode in Vector.

## Verified Routing Delivery

Routing was verified in two layers:

1. Deterministic local tests with the real `timberio/vector:0.45.0-debian`
   container.
2. Live Kafka -> Vector -> Kafka -> Argo delivery using synthetic
   `routing_test: true` records.

The live route-verification path is:

```text
synthetic route-test payload
  -> Confluent raw topic: alertmanager-events
  -> vector-alertmanager-normalizer
  -> Confluent normalized topic: alertmanager-events-triage
  -> vector-alertmanager-triage-kafka EventSource
  -> vector-routing-verification Sensor
  -> vector-routing-verification WorkflowTemplate
```

Verified live route cases:

| Case | Routing signal | Verified target |
|---|---|---|
| Application service alert | `namespace=payments`, `service=checkout-api`, `event_type=grafana-alert` | `aks-sre-triage-agent` |
| Platform Kubernetes event | `namespace=platform-tools`, `pod=load-test-runner-*`, `reason=FailedScheduling` | `platform-ops-agent` |
| Security alert | `namespace=platform-security`, `service=admission-controller`, `severity=critical` | `security-hardening-agent` |
| Unknown owner fallback | Missing stable `service` owner in `namespace=unlabelled-apps` | `sre-triage-agent` |

The route-verification workflow records `target_agent`, `route_key`,
`routing_reason`, `event_type`, `namespace`, `service`, `pod`, `severity`, and
`dedupe_key`. It does not call GitLab, Teams, Mattermost, ServiceNow, or a real
agent.

Important limitation: the current production triage Sensor still passes
`body.alertmanager` into `alertmanager-triage`. That preserves compatibility
with the existing WorkflowTemplate, but it means the real triage workflow does
not yet consume the top-level `target_agent`, `route_key`, `routing_reason`, and
`automation_allowed` fields. The route-verification Sensor proves those fields
can be delivered through Argo; the production workflow contract still needs to
be updated before this is a complete agent-routing implementation.

## Argo Cleanup Plan

Once the normalized topic is the accepted path:

1. Disable the old raw `alertmanager-events` Sensor or restrict it to replay and
   debugging.
2. Change the primary alert workflow to accept the normalized envelope, not a
   raw Alertmanager-only payload.
3. Remove source-specific parsing from workflow scripts where Vector already
   provides top-level fields such as `namespace`, `pod`, `severity`,
   `target_agent`, and `dedupe_key`.
4. Move count-bounded duplicate suppression into Vector. Keep only durable
   incident grouping in the workflow or incident system.
5. Track routing decisions with `route_key`, `target_agent`, and
   `routing_reason` so Grafana dashboards can show which agent handled which
   class of alert.
6. Keep one final safety check in Argo for write-capable remediation. Vector can
   classify the event, but workflow service accounts still own the execution
   permissions.

## Pros and Cons

### Pros

- Cleaner event contracts for multiple observability producers.
- Less workflow churn from duplicate events.
- Better raw-vs-normalized topic separation.
- Easier onboarding for Grafana-native Kafka payloads.
- More reusable Confluent event management pattern.

### Cons

- Adds another runtime to operate and monitor.
- Deduplication state is not a durable incident database.
- Requires careful schema ownership.
- May overlap with Alloy if deployed too broadly.
- Needs security review for Confluent credentials and namespace placement.

## Suggested Spike

1. Deploy Vector in the management cluster with read access to raw Confluent
   topics and write access to new triage topics.
2. Start with `alertmanager-events` because its payload contract is smaller
   than OTLP Kubernetes events.
3. Configure Vector to consume `alertmanager-events`, normalize each record,
   optionally suppress obvious duplicates, and publish `alertmanager-events-triage`.
4. Add one Argo EventSource/Sensor pair that consumes only
   `alertmanager-events-triage`.
5. Compare workflow count, duplicate suppression, and operator readability
   against the current direct Sensor path.
6. Only then repeat the pattern for `k8s-events`.

In short:

```text
Alertmanager sends raw events to Kafka.
Vector turns raw events into automation-ready events.
Argo acts only on the cleaned topic.
```

## Visual Explainer

Open [`vector-confluent-event-management.html`](vector-confluent-event-management.html)
in a browser for the visual version of this recommendation.

## Handoff Bundle

Use [`handoff/`](handoff/) when another agent or work-environment implementer
needs to critique or repeat this pattern:

- [`handoff/CRITIQUE-PROMPT.md`](handoff/CRITIQUE-PROMPT.md) asks another
  agent to challenge the design before promotion.
- [`handoff/WORK-IMPLEMENTATION-PROMPT.md`](handoff/WORK-IMPLEMENTATION-PROMPT.md)
  is the implementation brief for a private/work environment.
- [`handoff/VERIFICATION-SUMMARY.md`](handoff/VERIFICATION-SUMMARY.md)
  separates public-spike proof from remaining private verification.

## Validation Notes

Before implementation:

- Validate the Vector Kafka source and sink settings against the target
  Confluent Cloud cluster.
- Validate any Vector Kubernetes manifests with the target cluster policy.
- Keep all real endpoints, API keys, tenant IDs, and private names out of this
  public repo.

Live deployment notes:

- The manifests are sanitized and expect existing Kubernetes Secrets for
  Confluent bootstrap, key, secret, and CA material.
- Do not commit rendered manifests that contain real bootstrap endpoints or
  credentials.
- Restart Vector after changing the referenced Kafka Secret so the pod receives
  the current environment values.
