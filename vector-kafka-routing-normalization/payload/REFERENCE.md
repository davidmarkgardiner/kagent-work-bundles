# Payload Reference

Use the implementation references in:

```text
../../observability/vector/examples/
../../observability/vector/manifests/
../../observability/vector/tests/
```

Normalized records should include:

```json
{
  "schema_version": "observability.triage.v1",
  "source": "alertmanager|grafana|alloy",
  "event_type": "prometheus-alert|grafana-alert|kubernetes-event",
  "cluster": "{{CLUSTER_NAME}}",
  "environment": "{{ENVIRONMENT}}",
  "namespace": "{{NAMESPACE}}",
  "service": "{{SERVICE_NAME}}",
  "pod": "{{POD_NAME}}",
  "severity": "critical|warning|info",
  "target_agent": "{{TARGET_AGENT}}",
  "route_key": "{{ROUTE_KEY}}",
  "routing_reason": "{{ROUTING_REASON}}",
  "automation_allowed": false,
  "automation_policy": "default-deny",
  "incident_candidate": false,
  "dedupe_key": "{{CLUSTER}}:{{NAMESPACE}}:{{SERVICE}}:{{ALERT_NAME}}",
  "raw_topic": "{{RAW_TOPIC}}",
  "raw": {}
}
```

Production automation must remain default-deny unless an explicit Argo-side
allowlist grants write-capable remediation.
