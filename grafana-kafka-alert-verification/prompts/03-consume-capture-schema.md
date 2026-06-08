# Prompt 03 - Consume Kafka Record And Capture Payload

Use this only after `ALERT_RULE: firing`.

```text
Consume the Kafka record produced by the Grafana smoke alert and capture the
payload shape.

Use a fresh consumer group so previous offsets do not hide new events:

verify-grafana-alert-{{TIMESTAMP}}

Preferred consume order:

1. Confluent CLI, if available.
2. kcat, if available.
3. Argo Events EventSource logs, if this is the cluster-side consume path.
4. Approved internal Kafka consumer service.

Find the record for:

ConfluentKafkaFiringSmoke

Capture:

- topic
- partition
- offset
- Kafka timestamp
- raw JSON payload
- payload SHA256

Save the raw payload to the approved work evidence location. Do not commit or
paste secret values.

Then validate the payload against:

payload/grafana-kafka-alert.schema.json

If validation fails, report the missing/extra/type-mismatched fields and propose
the minimal schema change. Do not silently change the contract.

Return:

KAFKA_RECORD: consumed | blocked
KAFKA_METADATA: topic_partition_offset_timestamp
PAYLOAD_CAPTURED: yes | blocked
PAYLOAD_EVIDENCE_PATH: path_or_not_available
PAYLOAD_SHA256: sha256_or_not_available
SCHEMA_VALIDATION: passed | update_required | blocked
SCHEMA_DELTA: summary_or_none
OUTPUT_SANITIZED: yes
```
