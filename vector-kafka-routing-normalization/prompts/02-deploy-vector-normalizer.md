# Prompt 02: Deploy Vector Normalizer

Adapt the public-safe manifests from:

```text
../../observability/vector/manifests/
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
DEDUPE_STAGE: present
NEXT_ACTION:
```
