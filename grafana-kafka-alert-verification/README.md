# Grafana Kafka Alert Verification

## TL;DR

This bundle verifies the work-side Grafana Alerting to Confluent Kafka path
after the Kafka REST Proxy contact point connects successfully.

It is not enough for the contact point test to pass. The work agent must prove a
real alert fires, consume the Kafka record, capture the payload, validate the
payload shape, and decide whether schema validation can be enabled safely.

## What This Feature Does

- Checks required environment variables before live work starts.
- Discovers Grafana MCP/tooling access.
- Confirms the Grafana Kafka contact point.
- Creates or uses a temporary always-firing Grafana alert.
- Routes the smoke alert to the Kafka contact point.
- Consumes the produced Kafka event.
- Captures the raw payload and metadata.
- Validates the payload against a draft JSON Schema.
- Records the cluster-side consumer plan.
- Records whether broker-side schema validation is safe now or requires a
  bridge/serializer.

## Copyable Examples

The bundle includes example files the work agent can adapt:

```text
examples/argo-events/native-grafana-kafka-eventsource.yaml
examples/argo-events/native-grafana-kafka-sensor.yaml
examples/argo-events/native-grafana-alert-workflowtemplate.yaml
examples/schema/sample-grafana-kafka-alert.json
examples/schema/validate-sample-payload.sh
payload/grafana-kafka-alert.schema.json
```

These are examples, not production-ready manifests. The work agent must replace
placeholders, validate the installed Argo Events API version, and dry-run/apply
only in the approved work environment.

## Evidence To Produce

- Environment variable preflight result, without values.
- Grafana MCP/tool list.
- Grafana contact point name/UID and redacted settings.
- Alert rule name, UID, state, and evaluation timestamp.
- Kafka topic, partition, offset, and timestamp.
- Raw payload saved in the work evidence location.
- Schema validation result.
- Consumer path used: Confluent CLI, `kcat`, Argo Events, service, or bridge.
- Broker-side schema validation decision and rationale.
- Cleanup result.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Give `WORK-AGENT-START-PROMPT.md` to the work-side agent.
3. The agent must run `prompts/01-preflight-env-tools.md` before live changes.
4. The agent should review `examples/` before creating any Argo consumer path.
5. The agent then runs the remaining prompts in order.
6. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The bundle is complete only when a real Grafana firing alert has produced a
Kafka record that is consumed and captured at the cluster side, and the schema
validation decision is based on that actual payload.
