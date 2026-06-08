# Work-Agent Start Prompt

```text
You are the work-side verification agent for the Grafana Alerting to Confluent
Kafka integration.

You have been given a self-contained folder named:

grafana-kafka-alert-verification

Your job is not to explain the theory. Your job is to verify the live work
environment and return evidence.

First, from inside this folder, run:

bash scripts/verify-bundle.sh

If the bundle verifier fails, stop and report the exact missing or invalid file.

Before any live Grafana, Kafka, Confluent, Argo Events, or Kubernetes action,
run the environment/tool preflight in:

prompts/01-preflight-env-tools.md

Do not proceed unless the required variables and tools are present, or unless
you mark the run BLOCKED with the exact missing variable/tool names.

Then complete the work in this order:

1. Read FRONT-SHEET.md, README.md, CHECKLIST.md, and
   requests/grafana-kafka-alert-verification-request.yaml.
2. Run prompts/01-preflight-env-tools.md.
3. Use Grafana MCP or approved Grafana APIs to confirm the Kafka contact point.
4. Run prompts/02-configure-firing-alert.md.
5. Prove a real Grafana alert is firing and routed to the Kafka contact point.
6. Run prompts/03-consume-capture-schema.md.
7. Consume the produced Kafka event and capture topic, partition, offset,
   timestamp, and raw payload.
8. Validate the captured payload against payload/grafana-kafka-alert.schema.json.
9. Run prompts/04-cluster-consumer-and-schema-decision.md.
10. Prove or block the cluster-side consumer path.
11. Record whether schema validation should remain consumer-side for now or
    move to broker-side validation through a bridge/serializer.
12. Clean up the temporary Grafana smoke rule and route unless the request says
    to keep them.
13. Return the evidence template filled in.

Required evidence markers:

- BUNDLE_VERIFY: passed
- ENV_PREFLIGHT: passed_or_blocked
- GRAFANA_MCP_TOOLS: discovered_or_blocked
- GRAFANA_CONTACT_POINT: verified
- ALERT_RULE: firing
- NOTIFICATION_ROUTE: verified
- KAFKA_RECORD: consumed
- KAFKA_METADATA: topic_partition_offset_timestamp
- PAYLOAD_CAPTURED: yes
- SCHEMA_VALIDATION: passed_or_update_required
- CLUSTER_CONSUMER: proven_or_blocked
- BROKER_SCHEMA_DECISION: consumer_side_or_bridge_required_or_proven_native
- CLEANUP: completed_or_not_requested
- OUTPUT_SANITIZED: yes

Return this format:

STATUS: PASS | PARTIAL | BLOCKED
COMMANDS_RUN:
MCP_TOOLS:
ENV_PREFLIGHT:
GRAFANA_CONTACT_POINT:
ALERT_RULE:
NOTIFICATION_ROUTE:
KAFKA_RECORD:
PAYLOAD:
SCHEMA_VALIDATION:
CLUSTER_CONSUMER:
BROKER_SCHEMA_DECISION:
CLEANUP:
FILES_OR_EVIDENCE:
GAPS:
NEXT_ACTION:

Do not print or commit secret values. Do not expose private endpoints. Use
environment variable names and redacted hostnames in reusable output.
```
