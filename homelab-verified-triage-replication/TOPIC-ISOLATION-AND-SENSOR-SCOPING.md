# Kafka topic isolation and exact Sensor scoping

Use this handoff when the shared Kafka topic also carries LGTM, Alertmanager, or
other telemetry records. The goal is precise: only the approved worker-cluster
log/event evidence from the approved proof namespace may create a triage
workflow.

## Non-negotiable model

A Kafka consumer group is an **offset and load-sharing boundary**. It is not a
content filter. If the Argo EventSource shares a consumer group with another
application, partitions are divided between consumers and triage can miss its
own records. If it uses its own group on a shared topic, it reads the full topic
and the Sensors must reject unrelated records.

The preferred production shape is therefore:

```text
worker Alloy + Vector -> dedicated evidence-triage topic
LGTM / Alertmanager   -> separate alert topic
Argo EventSource      -> unique triage consumer group on evidence-triage topic
```

Do not share the triage consumer group with LGTM or Alertmanager consumers.

## What the shipped bundle already enforces

Both Sensors filter before they create a Workflow. A record must match all of
these fields:

| Field | Required value |
|---|---|
| `body.schema_version` | `observability.triage.v2` |
| `body.automation_allowed` | `false` |
| `body.cluster` | `red` |
| `body.namespace` | `agentic-triage-proof` |
| `body.signal_kind` | `log` for `red-log-triage`; `event` for `red-event-triage` |
| `body.reason` | Event Sensor only: the explicit incident-reason allow-list |

Therefore an LGTM payload, an Alertmanager-shaped payload, a v3 envelope, a
different cluster, or a different namespace does not create a triage workflow.
It may still be read and offset-committed by an EventSource using a shared topic;
that is why topic separation is preferable.

## Work-agent changes before apply

Make these four values agree in `config/01-alloy.yaml`, `config/02-vector.yaml`,
and `config/03-argo.yaml`:

| Value | Required choice |
|---|---|
| Worker cluster | The exact human/operator cluster name carried in `body.cluster` |
| Source namespace | One approved smoke-test namespace first; expand only after proof |
| Kafka topic | A dedicated evidence-triage topic if available; otherwise the approved shared topic |
| Consumer group | A unique group owned by this EventSource, never an LGTM consumer group |

For a work smoke test, set the namespace filter to the dedicated smoke namespace.
The current smoke labels are not a Sensor boundary because they are not carried
as an explicit envelope field. Namespace plus cluster is the hard boundary.

When moving beyond the smoke namespace, change both the Alloy collection scope
and both Sensor `body.namespace` allow-lists together. Do not broaden one and
forget the other.

## Required EventSource settings

Keep these properties in the work EventSource:

```yaml
topic: "{{EVIDENCE_TRIAGE_TOPIC}}"
consumerGroup:
  groupName: "{{EVIDENCE_TRIAGE_CONSUMER_GROUP}}"
  oldest: false
```

`oldest: false` prevents a new/restarted consumer group from intentionally
starting at the historical topic backlog. It is not a substitute for the Sensor
filters or Alloy position persistence.

## Proof before enabling real namespaces

Use fresh timestamps and inspect created Workflows after each case:

1. Send a v2 log from the approved smoke namespace: exactly one log-triage
   Workflow may be created.
2. Send a v2 event from the approved smoke namespace with an allow-listed
   reason: exactly one event-triage Workflow may be created.
3. Send a valid-looking v2 record from another namespace: no triage Workflow
   may be created.
4. Replay an LGTM/Alertmanager-shaped record from the shared topic: no triage
   Workflow may be created.
5. Repeat the approved record: dedupe must prevent a second agent/ticket path.

Use the Workflow label to make the assertion deterministic:

```bash
kubectl -n argo-events get workflows \
  -l app.kubernetes.io/part-of=alloy-vector-kafka-triage
```

Capture EventSource logs and the Vector Kafka-produced counter with each case.
A Sensor filter prevents workflow creation; it does not prove that the correct
producer wrote the record, which is why the producer-side Vector envelope and
topic/consumer-group ownership must also be verified.

## Do not do this

- Do not point the triage EventSource at an LGTM consumer group.
- Do not use a schema-only filter when multiple clusters share the topic.
- Do not broaden Alloy to all namespaces while the Sensor still has a smoke-only
  namespace filter, or the result will be silent drops and confusing metrics.
- Do not treat a lack of workflows as proof of correct filtering without running
  both positive and negative test records.
