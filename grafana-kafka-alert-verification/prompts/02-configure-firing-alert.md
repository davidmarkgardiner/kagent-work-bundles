# Prompt 02 - Configure And Prove A Firing Grafana Alert

Use this only after `ENV_PREFLIGHT: passed`.

```text
Verify the Grafana Kafka contact point and create or reuse a temporary
always-firing smoke alert.

Use Grafana MCP if write-capable tools are available. If Grafana MCP is
read-only, use the approved Grafana API/UI path and record that decision.

Tasks:

1. Read back the contact point named by GRAFANA_CONTACT_POINT_NAME.
2. Confirm it is a Kafka REST Proxy contact point.
3. Confirm the configured topic matches CONFLUENT_TOPIC.
4. Confirm credentials are present without exposing values.
5. Create or reuse a temporary Grafana-managed alert rule:
   - name: ConfluentKafkaFiringSmoke
   - query: vector(1), or equivalent always-true test query
   - label: route_to=confluent-kafka-rest
   - label: severity=warning
   - annotation summary: Grafana to Confluent Kafka firing smoke
6. Create or verify a notification route:
   - matcher: route_to=confluent-kafka-rest
   - target contact point: GRAFANA_CONTACT_POINT_NAME
7. Wait at least one evaluation interval.
8. Verify the alert state is firing in Grafana.

Return:

GRAFANA_CONTACT_POINT: verified | blocked
CONTACT_POINT_UID: uid_or_not_available
CONTACT_POINT_TOPIC: redacted_or_topic_name
ALERT_RULE: firing | blocked
ALERT_RULE_UID: uid_or_not_available
NOTIFICATION_ROUTE: verified | blocked
GRAFANA_MCP_USED: yes_or_no
OUTPUT_SANITIZED: yes

Do not proceed to Kafka consumption until ALERT_RULE is firing.
```
