# GitLab Ticket: Stream Kubernetes Events To Kafka With Grafana Alloy

## Summary

Configure Grafana Alloy on a workload cluster to watch Kubernetes Events and
publish them to Kafka for downstream Argo Events, schema validation, and SRE
triage workflows.

## Feature

Use Alloy as the workload-cluster event forwarder:

```text
Kubernetes Events
  -> Grafana Alloy loki.source.kubernetes_events
  -> loki.process enrichment and filtering
  -> otelcol.receiver.loki bridge
  -> otelcol.processor.batch
  -> otelcol.exporter.kafka
  -> Kafka topic
  -> Argo Events Kafka EventSource or approved consumer
```

The repo already has a public-safe starting point:

```text
observability/confluent-cloud-pipeline/workload-cluster/01-alloy-secret.md
observability/confluent-cloud-pipeline/workload-cluster/02-alloy-config.yaml
observability/confluent-cloud-pipeline/workload-cluster/03-alloy-deployment.patch.yaml
```

## Why This Is Feasible

Grafana Alloy supports `loki.source.kubernetes_events`, which tails Kubernetes
Events from the Kubernetes API and converts them into log lines. Alloy also
supports `otelcol.exporter.kafka`, which sends telemetry logs to Kafka. The
current repo pattern bridges Loki log entries into OTel logs and batches them
before Kafka export.

References:

- Grafana Alloy `loki.source.kubernetes_events`: https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.kubernetes_events/
- Grafana Alloy `otelcol.exporter.kafka`: https://grafana.com/docs/alloy/latest/reference/components/otelcol/otelcol.exporter.kafka/

## Scope

- Deploy or patch Alloy in the workload cluster namespace approved for
  observability, normally `monitoring`.
- Grant the Alloy service account read-only access to Kubernetes Events and the
  minimum discovery resources required by the component.
- Configure the Kafka exporter using Kubernetes Secret-backed environment
  variables.
- Produce Kubernetes Event records to a dedicated Kafka topic, for example
  `{{CONFLUENT_K8S_EVENTS_TOPIC}}`.
- Prove at least one synthetic or naturally occurring Kubernetes Event arrives
  at Kafka.
- Capture the consumed payload shape and decide whether schema validation should
  be consumer-side first or enforced at the broker after the wire format is
  proven.

## Out Of Scope

- Do not commit rendered Secrets.
- Do not commit real Kafka brokers, API keys, API secrets, tenant IDs, cluster
  IDs, private hostnames, or internal IPs.
- Do not enable broker-side schema validation until the actual Alloy-produced
  Kafka record shape is captured from the target environment.
- Do not grant Alloy Kubernetes write permissions.

## Implementation Notes

Start from the checked-in manifests and replace placeholders only in the target
environment:

```text
{{WORKLOAD_KUBE_CONTEXT}}
{{CONFLUENT_BOOTSTRAP}}
{{CONFLUENT_K8S_EVENTS_TOPIC}}
{{CONFLUENT_SA_KEY}}
{{CONFLUENT_SA_SECRET}}
{{CLUSTER_NAME}}
{{CLUSTER_ENVIRONMENT}}
{{CLUSTER_REGION}}
```

The Alloy config should keep:

```text
loki.source.kubernetes_events "cluster_events"
loki.process "enrich"
otelcol.receiver.loki "bridge"
otelcol.processor.batch "events"
otelcol.exporter.kafka "confluent"
```

Use batching before Kafka export so event bursts do not create excessive small
Kafka sends.

## Evidence Required

- Environment variable and Secret preflight, without values.
- Alloy ConfigMap rendered with placeholders replaced in the target environment.
- Alloy Deployment ready status.
- Alloy ServiceAccount, ClusterRole, and ClusterRoleBinding applied.
- Alloy logs showing Kubernetes Event source startup.
- Kafka exporter logs showing successful publish or no export errors.
- Kafka consumer proof with topic, partition, offset, and timestamp.
- Captured redacted payload for at least one Kubernetes Event.
- Argo Events Kafka EventSource proof, if the target path consumes from Argo.
- Schema decision recorded.
- Cleanup decision recorded for any synthetic test event.

## Suggested Smoke Test

Create a harmless Kubernetes Event in a non-production namespace, or use an
approved naturally occurring event. Then consume the Kafka topic and record the
first matching event.

Example synthetic event approach:

```yaml
apiVersion: events.k8s.io/v1
kind: Event
metadata:
  name: alloy-k8s-event-manual-{{RUN_ID}}
  namespace: {{TEST_NAMESPACE}}
regarding:
  apiVersion: v1
  kind: Namespace
  name: {{TEST_NAMESPACE}}
  namespace: {{TEST_NAMESPACE}}
reason: AlloyKafkaSmoke
note: Alloy Kubernetes Event to Kafka smoke test {{RUN_ID}}
type: Normal
action: ManualSmoke
reportingController: {{REPORTING_CONTROLLER}}
reportingInstance: {{REPORTING_INSTANCE}}
eventTime: "{{EVENT_TIME_RFC3339_MICRO}}"
```

Consumer proof can use one of:

```text
confluent kafka topic consume
kcat
Argo Events Kafka EventSource logs
approved internal Kafka consumer
```

## Acceptance Criteria

- `ENV_PREFLIGHT: passed_or_blocked`
- `ALLOY_CONFIG_RENDERED: yes`
- `ALLOY_RBAC_READ_ONLY: yes`
- `ALLOY_DEPLOYMENT_READY: yes`
- `K8S_EVENT_SOURCE_STARTED: yes`
- `KAFKA_EXPORTER_CONFIGURED: yes`
- `KAFKA_RECORD_CONSUMED: yes`
- `PAYLOAD_CAPTURED: yes`
- `ARGO_EVENTSOURCE_CONSUMED: yes_or_not_required_or_blocked`
- `SCHEMA_DECISION: consumer_side_or_broker_side_or_blocked`
- `OUTPUT_SANITIZED: yes`

## Blockers To Record

- Kafka API key lacks produce permission for `{{CONFLUENT_K8S_EVENTS_TOPIC}}`.
- Network policy blocks Alloy egress to Kafka brokers.
- TLS/SASL settings do not match the target Kafka provider.
- Alloy config fails validation for the installed Alloy version.
- Kubernetes RBAC does not allow watching Events.
- Topic schema validation rejects Alloy OTLP JSON records.

## Done Means

The ticket is complete when the team can show a real Kubernetes Event emitted
from the workload cluster, consumed from Kafka with topic/partition/offset, and
mapped to a documented payload/schema decision for downstream Argo/SRE
automation.
