# Prompt 01 - Environment And Tool Preflight

Use this before any live action.

```text
You are verifying readiness for the Grafana Alerting to Confluent Kafka proof.

Do not run Grafana, Kafka, Confluent, Kubernetes, Argo Events, or schema writes
until this preflight is complete.

Check that the required environment variables are present. Do not print values.
Only print present/missing variable names.

Required variables:

- GRAFANA_CONTACT_POINT_NAME
- CONFLUENT_TOPIC
- CONFLUENT_CLUSTER_ID
- CONFLUENT_BOOTSTRAP
- CONFLUENT_KAFKA_API_KEY
- CONFLUENT_KAFKA_API_SECRET
- CONSUMER_GROUP_PREFIX

Optional variables:

- GRAFANA_CONTACT_POINT_UID
- GRAFANA_URL
- GRAFANA_FOLDER_UID
- WORK_K8S_CONTEXT
- ARGO_EVENTS_NAMESPACE
- CONFLUENT_EVENTSOURCE_NAME
- SCHEMA_REGISTRY_ENDPOINT
- SCHEMA_REGISTRY_API_KEY
- SCHEMA_REGISTRY_API_SECRET
- CONFLUENT_SCHEMA_SUBJECT

Discover available tools:

1. Grafana MCP tools.
2. Kafka consume tool: Confluent CLI, kcat, Argo Events logs, or approved
   internal consumer.
3. Kubernetes/AKS MCP or kubectl access for cluster-side consumer verification.
4. Optional GitLab MCP if evidence needs to be committed to a work repo.

Return:

ENV_PREFLIGHT: passed | blocked
PRESENT_VARIABLES: names only
MISSING_VARIABLES: names only
GRAFANA_MCP_TOOLS: discovered_or_blocked
KAFKA_CONSUME_TOOL: confluent_cli_or_kcat_or_argo_or_service_or_blocked
CLUSTER_TOOL: discovered_or_blocked
OUTPUT_SANITIZED: yes

If any required variable is missing, stop and return BLOCKED.
```
