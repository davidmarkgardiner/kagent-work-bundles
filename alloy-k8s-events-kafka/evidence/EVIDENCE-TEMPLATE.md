# Evidence - Alloy Kubernetes Events To Kafka

## Run Metadata

```text
RUN_ID:
DATE:
WORKLOAD_KUBE_CONTEXT:
TEST_NAMESPACE:
MONITORING_NAMESPACE:
ARGO_EVENTS_NAMESPACE:
ARGO_WORKFLOWS_NAMESPACE:
```

## Markers

```text
ENV_PREFLIGHT:
ALLOY_NAMESPACE_SCOPED:
ALLOY_RBAC_READ_ONLY:
ALLOY_DEPLOYMENT_READY:
K8S_EVENT_TRIGGERED:
ALLOY_EVENT_OBSERVED:
KAFKA_RECORD_CONSUMED:
ARGO_EVENTSOURCE_CONSUMED:
ARGO_SENSOR_TRIGGERED:
ARGO_WORKFLOW_TRIGGERED:
PAYLOAD_CAPTURED:
SCHEMA_DECISION:
CLEANUP:
OUTPUT_SANITIZED:
```

## Environment Preflight

```text
Required variables checked:
Missing variables:
Secret source:
Values printed: no
```

## Alloy

```text
ConfigMap:
Deployment:
ServiceAccount:
RBAC:
Namespace list:
Ready status:
Log evidence:
Kafka exporter errors:
```

## Kafka

```text
Topic:
Consumer group:
Partition:
Offset:
Timestamp:
Consumer method:
```

## Argo Events

```text
EventSource:
EventSource status:
Sensor:
Sensor status:
Workflow created:
Workflow logs captured:
```

## Payload

Paste a redacted payload sample here:

```json
{}
```

## Schema Decision

```text
Decision:
Rationale:
Next action:
```

## Cleanup

```text
Smoke Job deleted:
Smoke Event retained:
Temporary namespace retained:
```
