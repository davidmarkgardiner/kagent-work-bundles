# Dual Kafka path smoke kit

This is the smallest end-to-end diagnostic for tomorrow. It excludes agents,
GitLab, claims, dedupe, and production triage logic.

```text
one Alloy source -> one Vector -> Kafka topic A -> EventSource A/group A -> Sensor A -> hello Workflow A
                                -> Kafka topic B -> EventSource B/group B -> Sensor B -> hello Workflow B
```

The same smoke log is sent to both Kafka sinks. If one hello Workflow fires and
the other does not, Alloy and Vector are already proven; compare only the
failing topic, ACL, EventSource, or consumer group. If neither fires, start at
Alloy/Vector. If both fire, basic transport is sound.

## Scope and safety

- Collects only pod logs from `dual-kafka-smoke`.
- Forwards only messages containing `DUAL-KAFKA-SMOKE`.
- Creates only short-lived `hello` Workflows in `argo-events`.
- Does not call an agent, create a ticket, or change the existing triage path.
- Uses existing `monitoring/alloy`, `argo-events/argo-events-sa`, EventBus
  `default`, and `argo-events/confluent-credentials` prerequisites.

## Values to replace

Replace these placeholders before apply:

| Placeholder | Meaning |
|---|---|
| `{{KAFKA_BOOTSTRAP}}` | Approved Kafka bootstrap endpoint |
| `{{KAFKA_TOPIC_A}}` / `{{KAFKA_TOPIC_B}}` | Two distinct diagnostic topics |
| `{{KAFKA_GROUP_A}}` / `{{KAFKA_GROUP_B}}` | Two unique EventSource-owned consumer groups |

Do not share either consumer group with LGTM or Alertmanager. A consumer group
manages offsets/load sharing; it does not filter record content.

## Run

```bash
bash scripts/deploy.sh --context <ctx>
bash scripts/verify.sh --context <ctx>
bash scripts/smoke.sh  --context <ctx>
bash scripts/teardown.sh --context <ctx>
```

Success is one hello Workflow from Sensor A and one from Sensor B for the same
unique marker. The Vector metrics expose independent `kafka_a` and `kafka_b`
counters to show whether both produces happened.

The marker Pod is now a manifest at `fixtures/dual-kafka-marker.yaml`; the
smoke script applies `fixtures/kustomization.yaml`. Replace its `images[].newName`
with the approved work registry image before running the smoke script.
