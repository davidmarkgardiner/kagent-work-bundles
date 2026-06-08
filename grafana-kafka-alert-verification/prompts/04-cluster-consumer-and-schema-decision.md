# Prompt 04 - Cluster Consumer And Schema Decision

Use this after a Kafka record has been consumed and the payload is captured.

```text
Prove or block the cluster-side consumer path and make the schema decision.

Cluster-side consumer options:

1. Argo Events Kafka EventSource with jsonBody=true.
2. Existing platform consumer service.
3. Temporary approved debug consumer.
4. Confluent CLI or kcat only as a short-term proof if no cluster consumer
   exists yet.

For native Grafana Kafka records, do not reuse bridge-specific filters that
expect:

- body.source
- body.alertmanager.status
- body.alertmanager.alerts

Native Grafana Kafka records are expected to use:

- body.client
- body.description
- body.details
- body.alert_state
- body.client_url
- body.incident_key

If Argo Events is used, propose or verify a native Grafana filter:

body.client == Grafana
body.alert_state == alerting

Copyable starting manifests are available in:

- examples/argo-events/native-grafana-kafka-eventsource.yaml
- examples/argo-events/native-grafana-kafka-sensor.yaml
- examples/argo-events/native-grafana-alert-workflowtemplate.yaml

Adapt those examples only after replacing placeholders and validating them
against the installed Argo Events and Argo Workflows versions.

Schema decision:

1. If the native Grafana contact point only emits plain JSON, keep validation
   consumer-side for now.
2. If broker-side schema validation is mandatory, recommend a bridge/normalizer
   that serializes with Schema Registry wire format before producing.
3. Only mark native broker-side schema validation as proven if a produced record
   is accepted with Confluent topic value schema validation enabled.

Return:

CLUSTER_CONSUMER: proven | blocked
CONSUMER_PATH: argo_events_or_service_or_cli_or_kcat_or_blocked
CONSUMER_FILTER: native_grafana_or_bridge_or_not_applicable
BROKER_SCHEMA_DECISION: consumer_side | bridge_required | proven_native_wire_format | blocked
RATIONALE: short evidence-based explanation
NEXT_ACTION: concrete next step
OUTPUT_SANITIZED: yes
```

After the native Kafka path is proven, validate the candidate alert queries in:

```text
examples/grafana-alerts/agentgateway-alert-candidates.md
```

Do not create durable 429/5xx/log-error rules until the work Grafana datasource
returns live series or the run is explicitly marked blocked by missing metrics
or labels.
