# Prompt 04: Run Grafana MCP End-To-End Test

This prompt proves the full work path, not just the lightweight
route-verification workflow.

Use Grafana MCP or approved Grafana APIs to create or trigger a safe temporary
alert that fires to the existing Manager/Grafana Kafka contact point.

Expected flow:

```text
Grafana test alert
  -> existing Manager/Grafana Kafka contact point
  -> Confluent raw topic
  -> Vector normalizer
  -> Confluent normalized topic
  -> Argo EventSource
  -> Argo Sensor
  -> production triage workflow
  -> kagent/kit agent analysis
  -> GitLab issue/ticket created
```

## Preconditions

Do not start unless these are already proven:

- Grafana MCP or approved Grafana API access works.
- Existing Kafka contact point is identified by name/UID.
- Notification policy/route sends the test alert to that contact point.
- Raw and normalized Kafka topics are known.
- Vector normalizer is healthy.
- Argo EventSource and Sensor are healthy.
- The production triage workflow is expected to create a GitLab issue/ticket.
- Any GitLab/project credentials are already configured in-cluster; do not
  print them.

## Test Alert Requirements

The alert must be safe and temporary:

- name includes `VectorRoutingE2ESmoke` or the approved work prefix
- route labels are explicit and non-production-impacting
- it fires quickly and can be cleaned up
- it does not page humans unless explicitly approved
- it includes labels needed for routing, such as `namespace`, `service`,
  `severity`, `environment`, and `cluster` where available

## Evidence To Capture

Capture names, IDs, and redacted metadata only:

- Grafana alert rule name/UID.
- Grafana contact point name/UID.
- Notification route/policy used.
- Raw Kafka topic, partition, offset, and timestamp.
- Normalized Kafka topic, partition, offset, and timestamp.
- Argo EventSource and Sensor log snippets showing the normalized event was
  consumed.
- Argo workflow name and phase.
- kagent/kit agent selected or invoked.
- GitLab issue/ticket URL or ID, redacted if required.
- Cleanup result for the temporary alert/routing objects.

## Pass Criteria

The test passes only when:

- GRAFANA_TEST_ALERT: firing
- MANAGER_CONTACT_POINT_DELIVERY: verified
- RAW_KAFKA_RECORD: produced
- NORMALIZED_KAFKA_RECORD: consumed
- ARGO_SENSOR_TRIGGER: verified
- TRIAGE_WORKFLOW: succeeded_or_expected_terminal_state
- KIT_AGENT_ANALYSIS: captured
- GITLAB_TICKET: created
- CLEANUP: completed_or_not_requested
- OUTPUT_SANITIZED: yes

If the route-verification workflow succeeds but no GitLab ticket is created,
return `PARTIAL`, not `PASS`.

Return:

```text
GRAFANA_TEST_ALERT: firing
MANAGER_CONTACT_POINT_DELIVERY: verified
RAW_KAFKA_RECORD:
NORMALIZED_KAFKA_RECORD:
ARGO_SENSOR_TRIGGER:
TRIAGE_WORKFLOW:
KIT_AGENT_ANALYSIS:
GITLAB_TICKET:
CLEANUP:
OUTPUT_SANITIZED: yes
GAPS:
NEXT_ACTION:
```
