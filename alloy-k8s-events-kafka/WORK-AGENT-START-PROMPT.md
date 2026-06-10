# Work Agent Start Prompt - Alloy Kubernetes Events To Kafka

You are verifying a one-namespace test pattern for Kubernetes Events flowing
through Grafana Alloy into Kafka and then into Argo Events.

Do not print, commit, or persist real Kafka brokers, API keys, API secrets,
tenant IDs, private hostnames, private IPs, or tokens. Use placeholders in any
returned documentation.

Before running anything, verify these are set in your shell or approved secret
store. Report only set/missing, never values:

```text
WORKLOAD_KUBE_CONTEXT
TEST_NAMESPACE
MONITORING_NAMESPACE
ARGO_EVENTS_NAMESPACE
ARGO_WORKFLOWS_NAMESPACE
ARGO_EVENTS_SERVICE_ACCOUNT
ARGO_WORKFLOWS_SERVICE_ACCOUNT
ARGO_EVENTS_EVENTBUS_NAME
CONFLUENT_BOOTSTRAP
CONFLUENT_K8S_EVENTS_TOPIC
CONFLUENT_SA_KEY
CONFLUENT_SA_SECRET
ALLOY_CONFLUENT_SECRET_NAME
CONFLUENT_CREDENTIALS_SECRET_NAME
CONFLUENT_CA_SECRET_NAME
CONSUMER_GROUP_PREFIX
CLUSTER_NAME
CLUSTER_ENVIRONMENT
CLUSTER_REGION
EXISTING_K8S_EVENTS_EVENTSOURCE_NAME
EXISTING_K8S_EVENTS_EVENT_NAME
```

Complete the work in this order:

1. Read `README.md`, `CHECKLIST.md`, `GITLAB-TICKET.md`, and this prompt.
2. Render the files in `examples/namespace-scoped/` using approved work values.
   Prefer `scripts/render-namespace-test.sh /tmp/alloy-k8s-events-kafka-rendered`.
3. Create or confirm the Kafka topic for `CONFLUENT_K8S_EVENTS_TOPIC`.
4. Create the Kubernetes Secret for Alloy Kafka credentials from the approved
   secret source. Do not commit the rendered Secret.
5. Apply `01-test-namespace.yaml`.
6. Apply `02-alloy-namespace-scoped.yaml`.
7. Wait for Alloy readiness and capture sanitized status.
8. Apply `05-argo-workflowtemplate.yaml`.
9. Apply `03-argo-kafka-eventsource.yaml`.
10. Apply `04-argo-kafka-sensor.yaml`.
11. Wait for the EventSource and Sensor to become ready.
12. If the EventSource logs show `not authorized to access this group`, stop
    using that smoke EventSource and either request the Kafka ACL or apply
    `07-existing-eventsource-sensor.yaml` against an existing authorized
    EventSource.
13. Apply `06-smoke-event.yaml` or create an equivalent harmless Event in the
    test namespace.
14. Confirm Alloy logs show Kubernetes event source startup and no Kafka export
    errors.
15. Confirm the Argo EventSource consumer group consumed at least one Kafka
    record from the topic.
16. Confirm the Sensor created an Argo Workflow.
17. Capture Workflow logs showing the consumed payload.
18. Decide whether schema validation remains consumer-side or can move to
    broker-side validation after the actual wire format is known.
19. Clean up the smoke Event and temporary no-filter Sensors unless the
    environment owner asks to keep them.
20. Fill in `evidence/EVIDENCE-TEMPLATE.md`.

Required evidence markers:

```text
ENV_PREFLIGHT: passed_or_blocked
ALLOY_NAMESPACE_SCOPED: yes
ALLOY_RBAC_READ_ONLY: yes
ALLOY_DEPLOYMENT_READY: yes_or_blocked
K8S_EVENT_TRIGGERED: yes_or_blocked
ALLOY_EVENT_OBSERVED: yes_or_blocked
KAFKA_RECORD_CONSUMED: yes_or_blocked
KAFKA_SMOKE_CONSUMER_GROUP: dedicated_or_blocked_by_acl_or_existing_authorized
ARGO_EVENTSOURCE_CONSUMED: yes_or_blocked
ARGO_SENSOR_TRIGGERED: yes_or_blocked
ARGO_WORKFLOW_TRIGGERED: yes_or_blocked
PAYLOAD_CAPTURED: yes_or_blocked
SCHEMA_DECISION: consumer_side_or_broker_side_or_blocked
CLEANUP: completed_or_not_requested
OUTPUT_SANITIZED: yes
```
