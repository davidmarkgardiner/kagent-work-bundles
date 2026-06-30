# Prompt 01: Preflight Environment And Tools

Check the environment before live changes. This is a hard discovery gate.

Assumption for this work run: Vector is already running, Confluent connectivity
already exists, and the Manager/Grafana contact point is already configured.
Your first job is to find and verify those existing resources.

Required tools:

```text
kubectl
jq
yq
docker or vector
confluent or approved Kafka client
Grafana MCP or approved Grafana API access
```

Required context:

```text
{{MGMT_KUBE_CONTEXT}}
{{ARGO_EVENTS_NAMESPACE}}
{{ALERTMANAGER_RAW_TOPIC}}
{{ALERTMANAGER_TRIAGE_TOPIC}}
{{KAFKA_BOOTSTRAP_SECRET_NAME}}
{{EXISTING_VECTOR_NAMESPACE}}
{{EXISTING_VECTOR_DEPLOYMENT_OR_RELEASE}}
{{GRAFANA_CONTACT_POINT_NAME_OR_UID}}
```

Tasks:

1. Confirm the management cluster context.
2. Confirm the Argo Events namespace and EventBus.
3. Confirm Kafka topic names and access method.
4. Confirm where Kafka credentials are stored.
5. Discover the existing Vector deployment, Helm release, or GitOps object.
6. Capture the existing Vector namespace, image name/tag, service account,
   ConfigMap/Secret references, resource requests/limits, probes, and exposed
   ports. Record names only for secrets.
7. Confirm where the Confluent connection strings and Kafka API credentials are
   referenced from Kubernetes. Record secret names and keys only, not values.
8. Confirm Grafana MCP or approved Grafana API access.
9. Use Grafana MCP/tooling to confirm the Manager/Grafana Kafka contact point,
   notification route, and safe test-alert mechanism. Record contact point name
   or UID and redact endpoint details.
10. Confirm whether Grafana-native and Alloy/Kubernetes topics exist.
11. Stop if any required variable/tool/resource is missing.

Return:

```text
ENV_PREFLIGHT: passed_or_blocked
MISSING_TOOLS:
MISSING_VARIABLES:
MISSING_RESOURCES:
CLUSTER_CONTEXT:
ARGO_NAMESPACE:
EXISTING_VECTOR: discovered_or_blocked
VECTOR_NAMESPACE:
VECTOR_DEPLOYMENT_OR_RELEASE:
VECTOR_IMAGE:
VECTOR_CONFIG_SOURCE:
VECTOR_SERVICE_ACCOUNT:
VECTOR_SECRET_REFS_NAMES_ONLY:
CONFLUENT_CONNECTION_SECRET: located_or_blocked
GRAFANA_MCP: available_or_blocked
MANAGER_CONTACT_POINT: verified_or_blocked
TOPICS:
SECRET_NAMES_ONLY:
NEXT_ACTION:
```

Do not print secret values.
