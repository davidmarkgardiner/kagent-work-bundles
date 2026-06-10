# Local Test - 2026-06-10

## Summary

Status: **pass with consumer-group ACL caveat**

The one-namespace Alloy to Kafka to Argo Events pattern was tested in the
home lab after `proxmox-k8s` came back online.

Static verification passed first:

```text
Bundle verifier:
  passed

Render helper:
  passed with safe dummy values

Rendered YAML:
  01-test-namespace.yaml docs=1
  02-alloy-namespace-scoped.yaml docs=6
  03-argo-kafka-eventsource.yaml docs=1
  04-argo-kafka-sensor.yaml docs=1
  05-argo-workflowtemplate.yaml docs=1
  06-smoke-event.yaml docs=1
```

## Preflight

```text
Local Confluent bootstrap env file:
  present

Required local variables found:
  CONFLUENT_BOOTSTRAP
  CONFLUENT_K8S_TOPIC
  CONFLUENT_SA_KEY
  CONFLUENT_SA_SECRET

Values printed:
  no
```

## Initial Cluster Blocker

Before Proxmox was started, the local cluster was unreachable:

```text
Kubernetes context:
  proxmox-k8s

Initial result:
  API unavailable

Error class:
  connect: host is down
  context deadline exceeded
```

After Proxmox was started:

```text
readyz:
  ok

Nodes:
  Ready
```

## Live Verification

```text
Test namespace:
  alloy-k8s-event-smoke

Alloy deployment:
  monitoring/alloy-k8s-events

Alloy namespace scope:
  alloy-k8s-event-smoke only

Alloy readiness:
  rollout successful

Alloy event source:
  watching events for namespace alloy-k8s-event-smoke

Kafka exporter:
  fetched metadata for topic k8s-events
```

The first Job-based event generator failed because `bitnami/kubectl:1.30` was
not available. That still generated Kubernetes Warning/Normal Events. The
bundle now uses the direct `events.k8s.io/v1` Event shape that succeeded in the
home-lab run.

Manual event:

```text
Event:
  alloy-k8s-event-manual-20260610100633

Reason:
  AlloyKafkaSmoke

Message:
  Alloy Kubernetes Event to Kafka manual smoke 20260610100633
```

Kafka/Argo proof:

```text
Preferred dedicated smoke EventSource:
  alloy-k8s-events-kafka

Preferred smoke consumer group:
  home-alloy-k8s-events-alloy-k8s-events-smoke

Result:
  blocked by Kafka ACL

Error:
  The client is not authorized to access this group

Fallback EventSource:
  confluent-kafka

Fallback event name:
  k8s-events

Fallback result:
  consumed and published to Argo event bus

Observed partition/offset:
  partition 1 offset 1258
```

Sensor and Workflow proof:

```text
Sensor:
  alloy-k8s-events-existing-consumer-smoke

Trigger:
  Successfully processed trigger alloy-k8s-event-workflow

Workflow:
  alloy-k8s-event-smoke-m7xmf

Workflow phase:
  Succeeded
```

Captured payload shape:

```json
{
  "resourceLogs": [
    {
      "resource": {},
      "scopeLogs": [
        {
          "scope": {},
          "logRecords": [
            {
              "body": {
                "stringValue": "{\"action\":\"ManualSmoke\",\"kind\":\"Namespace\",\"msg\":\"Alloy Kubernetes Event to Kafka manual smoke 20260610100633\",\"name\":\"alloy-k8s-event-smoke\",\"objectAPIversion\":\"v1\",\"reason\":\"AlloyKafkaSmoke\",\"reportingcontroller\":\"kagent-public.local/alloy-k8s-events-kafka\",\"reportinginstance\":\"codex-home-lab\",\"type\":\"Normal\"}"
              },
              "attributes": [
                {
                  "key": "pipeline",
                  "value": {
                    "stringValue": "alloy-k8s-events-kafka"
                  }
                },
                {
                  "key": "payload_type",
                  "value": {
                    "stringValue": "kubernetes-event-otlp"
                  }
                },
                {
                  "key": "event_reason",
                  "value": {
                    "stringValue": "AlloyKafkaSmoke"
                  }
                },
                {
                  "key": "namespace",
                  "value": {
                    "stringValue": "alloy-k8s-event-smoke"
                  }
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## Markers

```text
K8S_EVENT_TRIGGERED: yes
ALLOY_EVENT_OBSERVED: yes
KAFKA_RECORD_CONSUMED: yes
KAFKA_SMOKE_CONSUMER_GROUP: blocked_by_acl
ARGO_EVENTSOURCE_CONSUMED: yes_via_existing_authorized_eventsource
ARGO_SENSOR_TRIGGERED: yes
ARGO_WORKFLOW_TRIGGERED: yes
PAYLOAD_CAPTURED: yes
```

## Work-Side Action

For work, either:

1. Get the Kafka API key authorized for the dedicated smoke consumer group.
2. Reuse an existing authorized Argo Events Kafka EventSource and apply
   `07-existing-eventsource-sensor.yaml` only for the smoke run.

Do not leave broad fallback Sensors running after the smoke test.

## Cleanup

```text
Deleted:
  EventSource/alloy-k8s-events-kafka
  Sensor/alloy-k8s-events-kafka-smoke
  Sensor/alloy-k8s-events-existing-consumer-smoke
  Job/alloy-k8s-event-smoke
  failed Workflow/alloy-k8s-event-smoke-p2v2c

Left running:
  Deployment/monitoring/alloy-k8s-events
  Workflow/argo/alloy-k8s-event-smoke-m7xmf
```
