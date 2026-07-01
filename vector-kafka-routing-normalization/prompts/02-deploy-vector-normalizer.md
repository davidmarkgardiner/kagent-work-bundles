# Prompt 02: Deploy Vector Normalizer

Adapt the public-safe manifests from:

```text
payload/observability-vector/manifests/
```

Use approved work values for:

- namespaces
- Kafka bootstrap secret names
- topic names
- service accounts
- image registry/tag policy
- resource requests and limits

Before apply:

```bash
kubectl apply --dry-run=server -f <adapted-manifests>
```

Deploy only after dry run passes.

Vector must own the cleanup boundary. The config should make these stages clear
and testable:

```text
raw input
  -> schema/shape normalization
  -> status filter
  -> severity / namespace / service noise filter
  -> owner and route enrichment
  -> dedupe key generation
  -> duplicate suppression
  -> actionable Kafka sink
  -> optional metrics/quarantine sink for dropped events
```

The actionable Kafka sink must receive only records that should be reviewed by
an agent. Argo must not be used as the primary place to filter resolved alerts,
noise, malformed events, or duplicates.

Required checks:

```bash
kubectl -n {{ARGO_EVENTS_NAMESPACE}} rollout status deploy/vector-alertmanager-normalizer
kubectl -n {{ARGO_EVENTS_NAMESPACE}} get pods -l app.kubernetes.io/name=vector-alertmanager-normalizer
kubectl -n {{ARGO_EVENTS_NAMESPACE}} logs deploy/vector-alertmanager-normalizer --tail=80
```

Return:

```text
VECTOR_CONFIG: validated
K8S_DRY_RUN: passed
VECTOR_ROLLOUT: healthy
IMAGE:
PROBES:
FILTER_STAGE: present
NOISE_FILTER_STAGE: present
ROUTE_ENRICHMENT_STAGE: present
DEDUPE_STAGE: present
ACTIONABLE_SINK: present
QUARANTINE_OR_DROP_DECISION: captured
NEXT_ACTION:
```
