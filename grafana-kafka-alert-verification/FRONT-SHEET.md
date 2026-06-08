# Grafana Kafka Alert Verification Work-Agent Bundle

Purpose: hand a work-side agent a repeatable process to verify that Grafana
Alerting is producing real alert records to Confluent Kafka, capture the actual
payload shape, validate it locally, and decide how schema validation should be
enabled.

## One-Line Ask

Use the approved work environment to prove:

```text
Grafana alert rule fires
  -> notification policy routes to Kafka contact point
  -> Confluent topic receives the record
  -> cluster-side consumer reads the record
  -> actual payload shape is captured
  -> schema validation strategy is recorded
```

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/grafana-kafka-alert-verification-request.yaml`
5. `prompts/01-preflight-env-tools.md`
6. `prompts/02-configure-firing-alert.md`
7. `prompts/03-consume-capture-schema.md`
8. `prompts/04-cluster-consumer-and-schema-decision.md`
9. `payload/grafana-kafka-alert.schema.json`
10. `examples/argo-events/native-grafana-kafka-eventsource.yaml`
11. `examples/argo-events/native-grafana-kafka-sensor.yaml`
12. `examples/argo-events/native-grafana-alert-workflowtemplate.yaml`
13. `examples/schema/sample-grafana-kafka-alert.json`
14. `evidence/EVIDENCE-TEMPLATE.md`

## Definition Of Done

- Bundle verifier passes.
- Required environment variables are checked before any live action.
- Grafana MCP/tools are discovered and recorded.
- Grafana contact point is confirmed.
- A real Grafana alert rule is observed firing.
- Kafka record is consumed with topic, partition, offset, and timestamp.
- Raw payload is captured without secrets.
- Payload validates against the draft schema, or schema changes are proposed.
- Cluster-side consumer path is proven or blocked with the exact blocker.
- Copyable Argo EventSource, Sensor, and WorkflowTemplate examples are adapted
  or explicitly rejected with a reason.
- Broker-side schema validation decision is recorded.
- Temporary Grafana smoke rule and route are cleaned up.

## Key Safety Boundary

Do not expose API keys, Grafana credentials, private endpoints, tenant IDs, or
internal IPs. Use environment variable names and redacted hostnames in evidence.
Do not turn broker-side schema validation back on until the actual Grafana
payload and producer serialization path are proven.
