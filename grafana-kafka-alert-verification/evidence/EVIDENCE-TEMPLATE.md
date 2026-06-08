# Evidence Template

Use this template for the work-side closeout.

```text
STATUS: PASS | PARTIAL | BLOCKED

BUNDLE_VERIFY: passed | failed
ENV_PREFLIGHT: passed | blocked
OUTPUT_SANITIZED: yes | no

COMMANDS_RUN:
- {{COMMAND_OR_TOOL_CALL_WITHOUT_SECRET_VALUES}}

MCP_TOOLS:
- Grafana MCP: {{TOOLS_OR_BLOCKER}}
- Kubernetes/AKS MCP: {{TOOLS_OR_BLOCKER}}
- GitLab MCP: {{TOOLS_OR_NOT_USED}}

ENVIRONMENT_PREFLIGHT:
- Required variables present: {{VARIABLE_NAMES_ONLY}}
- Missing variables: {{VARIABLE_NAMES_ONLY_OR_NONE}}
- Secret values printed: no

GRAFANA_CONTACT_POINT:
- Name: {{GRAFANA_CONTACT_POINT_NAME}}
- UID: {{GRAFANA_CONTACT_POINT_UID}}
- Type: Kafka REST Proxy
- Redacted REST endpoint host: {{REDACTED_HOST_OR_NOT_CAPTURED}}
- Topic: {{CONFLUENT_TOPIC}}

ALERT_RULE:
- Name: ConfluentKafkaFiringSmoke
- UID: {{ALERT_RULE_UID}}
- State: firing | blocked
- Evaluation timestamp: {{TIMESTAMP}}

NOTIFICATION_ROUTE:
- Matcher: route_to = confluent-kafka-rest
- Contact point: {{GRAFANA_CONTACT_POINT_NAME}}
- Route verified: yes | no | blocked

KAFKA_RECORD:
- Consumed: yes | no | blocked
- Tool: Confluent CLI | kcat | Argo Events | service | other
- Topic: {{TOPIC}}
- Partition: {{PARTITION}}
- Offset: {{OFFSET}}
- Timestamp: {{KAFKA_TIMESTAMP}}

PAYLOAD:
- Raw payload evidence path: {{PATH}}
- Payload SHA256: {{SHA256}}
- Required fields present: yes | no
- alert_state: {{VALUE}}
- client: {{VALUE}}

SCHEMA_VALIDATION:
- Schema file: payload/grafana-kafka-alert.schema.json
- Result: passed | update_required | blocked
- Required schema change: {{SUMMARY_OR_NONE}}

CLUSTER_CONSUMER:
- Path: Argo Events | service | Confluent CLI | kcat | blocked
- Consumer group: {{GROUP_OR_NOT_CAPTURED}}
- EventSource/Sensor/service: {{NAME_OR_NOT_APPLICABLE}}
- Result: proven | blocked

BROKER_SCHEMA_DECISION:
- Decision: consumer_side | bridge_required | proven_native_wire_format | blocked
- Rationale: {{SHORT_RATIONALE}}

CLEANUP:
- Temporary alert rule removed: yes | no | not_requested
- Temporary notification route removed: yes | no | not_requested

GAPS:
- {{GAP_OR_NONE}}

NEXT_ACTION:
- {{NEXT_ACTION}}
```
