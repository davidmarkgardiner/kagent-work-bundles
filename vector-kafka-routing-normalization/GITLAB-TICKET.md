# GitLab Ticket: Vector Kafka Routing Normalization

## Summary

Implement and verify Vector-based normalization and routing between raw Kafka
observability topics and Argo Events.

## Problem

Alertmanager, Grafana-native Kafka notifications, and Alloy/Kubernetes events
arrive in different payload shapes. Argo workflows currently need to parse and
classify source-specific payloads, which makes routing, dedupe, and value
measurement harder.

## Proposed Change

Deploy Vector in the management cluster to:

- consume raw Kafka topics
- normalize events to `observability.triage.v1`
- filter resolved/noisy events
- suppress duplicates with `dedupe_key`
- assign `target_agent`, `route_key`, and `routing_reason`
- publish normalized topics consumed by Argo Events

For this work run, first reuse the existing Vector and Confluent setup:

- discover the existing Vector namespace, deployment/release, image, config
  source, service account, and secret references
- confirm the existing Confluent connection secret without printing values
- confirm Grafana MCP access
- confirm the Manager/Grafana Kafka contact point and safe test alert path

## Acceptance Criteria

- BUNDLE_VERIFY: passed
- ENV_PREFLIGHT: passed_or_blocked
- EXISTING_VECTOR: discovered
- VECTOR_IMAGE: captured
- VECTOR_NAMESPACE: captured
- CONFLUENT_CONNECTION_SECRET: located
- GRAFANA_MCP: available_or_blocked
- MANAGER_CONTACT_POINT: verified
- VECTOR_CONFIG: validated
- K8S_DRY_RUN: passed
- VECTOR_ROLLOUT: healthy
- RAW_KAFKA_RECORD: produced
- NORMALIZED_KAFKA_RECORD: consumed
- GRAFANA_TEST_ALERT: firing
- MANAGER_CONTACT_POINT_DELIVERY: verified
- ARGO_SENSOR_TRIGGER: verified
- TRIAGE_WORKFLOW: succeeded_or_expected_terminal_state
- KIT_AGENT_ANALYSIS: captured
- GITLAB_TICKET: created
- ROUTE_APP: verified
- ROUTE_PLATFORM: verified
- ROUTE_SECURITY: verified
- ROUTE_FALLBACK: verified
- DEDUPE: verified
- RESOLVED_FILTER: verified
- FULL_ENVELOPE_WORKFLOW: planned_or_implemented
- AUTOMATION_GATE: default_deny
- METRICS_PLAN: captured
- OUTPUT_SANITIZED: yes

## Non-Goals

- Do not enable write-capable automated remediation without an explicit Argo-side
  allowlist.
- Do not replace Kafka with Vector.
- Do not remove raw topics until replay/audit requirements are agreed.
