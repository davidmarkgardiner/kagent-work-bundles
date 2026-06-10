# Alloy Kubernetes Events To Kafka Test Pattern

This bundle gives a work agent a narrow, end-to-end test pattern for one
namespace:

```text
test namespace Kubernetes Event
  -> namespace-scoped Grafana Alloy event watcher
  -> Kafka topic
  -> Argo Events Kafka EventSource consumer group
  -> Argo Sensor
  -> Argo Workflow echoing the consumed payload
```

It is intentionally scoped to one namespace first. The work agent should prove
transport, payload shape, consumer group behaviour, and Argo triggering before
expanding collection to more namespaces or enabling broker-side schema
validation.

## Files

```text
GITLAB-TICKET.md
WORK-AGENT-START-PROMPT.md
CHECKLIST.md
evidence/EVIDENCE-TEMPLATE.md
examples/namespace-scoped/01-test-namespace.yaml
examples/namespace-scoped/02-alloy-namespace-scoped.yaml
examples/namespace-scoped/03-argo-kafka-eventsource.yaml
examples/namespace-scoped/04-argo-kafka-sensor.yaml
examples/namespace-scoped/05-argo-workflowtemplate.yaml
examples/namespace-scoped/06-smoke-event-job.yaml
scripts/render-namespace-test.sh
scripts/verify-bundle.sh
```

## Design Notes

Use `loki.source.kubernetes_events` with an explicit namespace list:

```alloy
loki.source.kubernetes_events "cluster_events" {
  namespaces = ["{{TEST_NAMESPACE}}"]
  job_name   = "kubernetes-events"
  log_format = "json"
  forward_to = [loki.process.enrich.receiver]
}
```

Grafana documents that an empty namespace list watches all namespaces. With an
explicit namespace list, Alloy only needs permissions to watch events for those
namespaces.

The test pattern therefore binds Alloy's service account to a Role in
`{{TEST_NAMESPACE}}`, not a broad ClusterRole.

## Evidence Flow

1. Render placeholders for the target environment.
2. Apply the test namespace.
3. Apply the namespace-scoped Alloy ConfigMap, Deployment, ServiceAccount, Role,
   and RoleBinding.
4. Apply the Argo WorkflowTemplate, EventSource, and Sensor.
5. Trigger a harmless Kubernetes Event in `{{TEST_NAMESPACE}}`.
6. Confirm Alloy logs show event collection and Kafka export has no errors.
7. Confirm the Argo EventSource consumer group consumes from Kafka.
8. Confirm the Argo Sensor creates a Workflow.
9. Capture the Workflow logs containing the Kafka payload.
10. Record the payload shape and schema decision.

Use the render helper to create a temporary apply directory:

```bash
work-agent-bundles/alloy-k8s-events-kafka/scripts/render-namespace-test.sh \
  /tmp/alloy-k8s-events-kafka-rendered
```

The rendered output may contain environment-specific Kafka endpoints and Secret
names. Do not commit it.

## Expansion Rule

Only expand beyond one namespace after the agent records:

```text
ALLOY_NAMESPACE_SCOPED: yes
KAFKA_RECORD_CONSUMED: yes
ARGO_WORKFLOW_TRIGGERED: yes
PAYLOAD_CAPTURED: yes
OUTPUT_SANITIZED: yes
```

Then move from one namespace to either an explicit namespace list or a
cluster-wide watch with a reviewed ClusterRoleBinding.
