# Home-Lab Verification - 2026-06-08

This note records the sanitized home-lab proof for the work-agent bundle.
Secrets, private endpoint values, and internal hostnames are intentionally
omitted or redacted.

## Summary

Status: **PASS / schema proven / Grafana MCP recovered**

The home lab proved:

```text
Grafana managed alert rule fired
  -> native Kafka REST Proxy contact point used Confluent Kafka topic
  -> Argo Events Kafka EventSource consumed the Kafka record
  -> existing bridge-specific Sensor rejected the record because the native
     Grafana schema does not contain body.source
```

This is enough to hand the work agent a concrete payload contract and a clear
next action: add a native Grafana Kafka Sensor or a normalizer/bridge before
using the existing Alertmanager triage Sensor.

Follow-up verification on 2026-06-08 11:42 BST also proved that the home-lab
Grafana MCP transport recovered and can query Grafana directly.

## Runtime Preflight

```text
Kubernetes context:
  proxmox-k8s

Grafana:
  namespace monitoring
  deployment/service running
  API health ok
  version 12.3.2

Grafana datasources:
  Alertmanager
  Loki
  Mimir Rule Sync Proof
  Prometheus

Grafana Kafka contact point:
  name confluent-kafka-rest-alerts
  type kafka
  apiVersion v3
  topic alertmanager-events
  REST proxy present
  username present
  password present

Argo Events:
  EventSource confluent-kafka Deployed=True
  existing alertmanager-events consumer running
```

## Grafana MCP Preflight

The in-cluster `kagent-grafana-mcp` RemoteMCPServer was temporarily unhealthy
during the original alert-to-Kafka verification window:

```text
RemoteMCPServer:
  kagent-grafana-mcp

Accepted:
  False

Reason:
  connection refused to the Grafana MCP service endpoint
```

The pod restarted at approximately `2026-06-08T10:26:48Z` and the
RemoteMCPServer reconciled to `Accepted=True` at `2026-06-08T10:27:39Z`.

Current verified state:

```text
RemoteMCPServer:
  kagent-grafana-mcp

Accepted:
  True

Grafana evidence agent:
  Accepted=True
  Ready=True

Smoke test:
  scripts/observability/smoke-grafana-mcp.sh --context {{KUBE_CONTEXT}}

Smoke result:
  MCP initialized
  list_datasources discovered
  query_prometheus discovered
  list_datasources returned Alertmanager, Loki, Mimir, and Prometheus
  count(up) returned 48
```

The original Kafka proof used the Grafana HTTP API directly because MCP was
transiently unavailable at that moment. For the work replay, use Grafana MCP as
the primary path and keep the approved Grafana API path as a fallback only if MCP
fails preflight.

## Smoke Alert Proof

Temporary Grafana alert rule:

```text
title:
  HomeConfluentKafkaFiringSmoke-{{TIMESTAMP}}

query:
  vector(1)

labels:
  route_to = confluent-kafka-rest
  severity = warning
  source = home-lab

notification receiver:
  confluent-kafka-rest-alerts

state:
  active/firing
```

Grafana alert state included:

```text
alertname = HomeConfluentKafkaFiringSmoke-{{TIMESTAMP}}
__grafana_receiver__ = confluent-kafka-rest-alerts
route_to = confluent-kafka-rest
severity = warning
source = home-lab
```

## Argo EventSource Evidence

The existing Argo Events Kafka EventSource consumed native Grafana records from
the Confluent topic:

```text
eventSourceName:
  confluent-kafka

eventName:
  alertmanager-events

eventSourceType:
  kafka

topic:
  alertmanager-events

observed offsets:
  partition 2 offset 3
  partition 5 offset 2
```

## Native Grafana Kafka Payload Shape

The consumed Argo Events body had this shape:

```json
{
  "topic": "alertmanager-events",
  "key": "",
  "partition": 5,
  "body": {
    "description": "[FIRING:1] HomeConfluentKafkaFiringSmoke-{{TIMESTAMP}} Kagent Alerting (confluent-kafka-rest warning home-lab)",
    "client": "Grafana",
    "details": "**Firing**\n\nValue: B0=1\nLabels:\n - alertname = HomeConfluentKafkaFiringSmoke-{{TIMESTAMP}}\n - grafana_folder = Kagent Alerting\n - route_to = confluent-kafka-rest\n - severity = warning\n - source = home-lab\nAnnotations:\n - summary = Home lab Grafana to Confluent Kafka firing smoke\nSource: {{GRAFANA_ALERT_URL}}\nSilence: {{GRAFANA_SILENCE_URL}}\n",
    "alert_state": "alerting",
    "client_url": "{{GRAFANA_ALERTING_LIST_URL}}",
    "incident_key": "{{INCIDENT_KEY_HASH}}"
  },
  "timestamp": "{{KAFKA_EVENT_TIMESTAMP}}",
  "headers": {}
}
```

Useful schema fields for a native Grafana Sensor:

```text
body.client
body.description
body.details
body.alert_state
body.client_url
body.incident_key
```

## Existing Sensor Result

The existing `confluent-alertmanager-triage` Sensor is intentionally
bridge-specific. It expects:

```text
body.source
body.alertmanager.status
body.alertmanager.alerts
```

It discarded the native Grafana record with:

```text
data filter error (path 'body.source' does not exist)
```

This confirms the work-side choice:

```text
Option A:
  add a native Grafana Kafka Sensor filtering on body.client and
  body.alert_state

Option B:
  add a normalizer/bridge that converts the native Grafana payload into the
  existing Alertmanager envelope
```

## Alert Query Discovery

Prometheus confirmed Agent Gateway metrics exist. Useful observed metric names:

```text
agentgateway_requests_total
agentgateway_request_duration_seconds_count
agentgateway_gen_ai_server_request_duration_count
grafana_alerting_notification_requests_total
```

Observed useful labels on `agentgateway_requests_total`:

```text
namespace
pod
route
backend
method
protocol
status
reason
gateway
listener
```

Loki confirmed Agent Gateway logs are queryable from namespace
`agentgateway-system`.

Candidate alert queries are captured in:

```text
examples/grafana-alerts/agentgateway-alert-candidates.md
```

## Cleanup

Cleanup completed:

```text
temporary Grafana alert rules deleted
temporary notification policy routes removed
```

## Remaining Gap

Confluent CLI consume was not used as the final payload evidence because the
local CLI session required re-login. The cluster-side Argo Events consumer did
capture the payload and is the stronger evidence for this handoff because the
work objective is cluster-side consumption.
