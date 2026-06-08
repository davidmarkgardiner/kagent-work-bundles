# GitLab Ticket: Verify Grafana Alerting To Confluent Kafka Payload And Schema

## Summary

Verify that Grafana Alerting is producing real alert events to Confluent Kafka,
capture the actual payload shape, and decide how schema validation should be
implemented.

## Feature

Grafana already connects to Kafka through the Kafka REST Proxy contact point.
The next step is to prove a real alert fires, the produced Kafka record can be
consumed at the cluster side, and the record shape is suitable for downstream
schema validation and routing.

## Evidence Required

- Required environment variable preflight result.
- Grafana MCP/tool discovery result.
- Kafka contact point name/UID and redacted configuration.
- Temporary alert rule state showing firing.
- Kafka topic, partition, offset, and timestamp.
- Captured raw payload.
- JSON Schema validation result.
- Cluster-side consumer proof or exact blocker.
- Broker-side schema validation decision.
- Cleanup result.

## Acceptance Criteria

- `ENV_PREFLIGHT: passed_or_blocked`
- `GRAFANA_CONTACT_POINT: verified`
- `ALERT_RULE: firing`
- `KAFKA_RECORD: consumed`
- `PAYLOAD_CAPTURED: yes`
- `SCHEMA_VALIDATION: passed_or_update_required`
- `CLUSTER_CONSUMER: proven_or_blocked`
- `BROKER_SCHEMA_DECISION: consumer_side_or_bridge_required_or_proven_native`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not enable broker-side schema validation until the actual Grafana payload and
producer serialization path are proven. If the native Grafana Kafka contact
point cannot produce Schema Registry wire-format records, use consumer-side
validation first or introduce a bridge/serializer.
