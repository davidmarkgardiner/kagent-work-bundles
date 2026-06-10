# Local Test - 2026-06-10

## Summary

Status: **blocked before cluster apply**

The static bundle was created for the one-namespace Alloy to Kafka to Argo
Events pattern. Local live execution could not proceed because the configured
home-lab Kubernetes API for `proxmox-k8s` was unreachable during the test
window.

Static verification did pass:

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
  06-smoke-event-job.yaml docs=4
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

## Cluster Blocker

```text
Kubernetes context:
  proxmox-k8s

Result:
  API unavailable

Error class:
  connect: host is down
  context deadline exceeded

Impact:
  Could not create the test namespace, Alloy deployment, Argo EventSource,
  Sensor, WorkflowTemplate, smoke Event Job, or live Kafka/Argo evidence.
```

## Next Live Verification Step

When `proxmox-k8s` is reachable again, start from:

```text
WORK-AGENT-START-PROMPT.md
examples/namespace-scoped/
```

Use a dedicated namespace and consumer group:

```text
TEST_NAMESPACE:
  alloy-k8s-event-smoke

CONSUMER_GROUP_PREFIX:
  home-alloy-k8s-events
```

The expected live proof remains:

```text
K8S_EVENT_TRIGGERED: yes
ALLOY_EVENT_OBSERVED: yes
KAFKA_RECORD_CONSUMED: yes
ARGO_EVENTSOURCE_CONSUMED: yes
ARGO_SENSOR_TRIGGERED: yes
ARGO_WORKFLOW_TRIGGERED: yes
PAYLOAD_CAPTURED: yes
```
