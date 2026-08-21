# 1. Worker Cluster — Alloy, Vector and Kafka

Do this section entirely on the approved worker cluster. The goal is not to
install every manifest in one go: first prove Alloy can collect from one safe
namespace, then prove Vector receives/redacts that signal, then prove Kafka
accepts it.

## 1.1 Discover before installing

Record the following in your private operator notes. Do not guess from the home
lab YAML.

```bash
kubectl --context {{WORKER_KUBECTL_CONTEXT}} get ns
kubectl --context {{WORKER_KUBECTL_CONTEXT}} get deploy -A | rg -i 'alloy|vector'
kubectl --context {{WORKER_KUBECTL_CONTEXT}} get crd | rg -i 'alloy|vector' || true
kubectl --context {{WORKER_KUBECTL_CONTEXT}} get networkpolicy -A
```

Confirm the approved image source/tag, namespace, service account, workload
identity, Secret/CA reference names, and GitOps owner. If Alloy or Vector
already exists, extend the existing managed installation only through its
owner's GitOps path—do not install a second collector that competes for logs.

## 1.2 Install Alloy only

Adapt the Alloy portion of
[`kustomize/base/worker.yaml`](../kustomize/base/worker.yaml) to the discovered
worker namespace and existing policy. Keep the scope to one non-production
namespace and read-only RBAC for `pods`, `pods/log` and `events`.

Before reconciliation/apply, review the rendered Alloy objects:

```bash
kubectl kustomize ../kustomize/overlays/pilot > /tmp/evidence-first-rendered.yaml
rg -n -C 2 "${ALLOY_DEPLOYMENT}|${WORKER_NAMESPACE}|pods/log|events|${VECTOR_SERVICE}" /tmp/evidence-first-rendered.yaml
kubectl --context "$WORKER_CONTEXT" apply --dry-run=server -f /tmp/evidence-first-rendered.yaml
```

Only reconcile/apply the Alloy resources after removing Vector resources from
the rendered change or after splitting the change in the approved GitOps PR.
The existing overlay is a complete pilot; it is not a safe instruction to
install both components together when isolating the worker proof.

## 1.3 Prove Alloy independently

```bash
bash scripts/check-worker-alloy-vector.sh --values /path/to/private/values.env --stage alloy
```

Pass criteria:

- Alloy Deployment is available.
- Its service account can get pods, pod logs and events only in the approved
  namespace.
- Its configuration selects that namespace and points at the intended Vector
  service endpoint.
- The Vector service has ready endpoints before sending any test signal.

Create one harmless log fixture in the approved namespace, with a unique run
marker, then inspect Alloy logs. Do not use real application secrets or a
production failure as the first test.

```text
ERROR E2E-{{RUN_ID}} controlled worker-path test token=not-a-real-token
```

Alloy proof is complete only when the marker is observed in the Alloy-to-Vector
path—not merely because the Alloy pod is running.

## 1.4 Install and prove Vector

Adapt the Vector portion of `kustomize/base/worker.yaml` against the discovered
image policy, namespace, secret references, storage class and NetworkPolicy.
Its input must be the Alloy OTLP service, and its Kafka sink must use the
approved topic and producer identity. Keep the redaction and bounded-envelope
transform; do not pass raw pod logs to Kafka.

Run a server-side dry run before applying the Vector-only change:

```bash
kubectl --context "$WORKER_CONTEXT" apply --dry-run=server -f "$VECTOR_ONLY_RENDERED_MANIFEST"
bash scripts/check-worker-alloy-vector.sh --values /path/to/private/values.env --stage vector
```

Pass criteria:

- Vector Deployment is available, its buffer PVC is bound if configured, and
  the Alloy-to-Vector service endpoint is ready.
- The controlled marker is accepted by the intended allow-list.
- The synthetic token is redacted before the Kafka sink.
- Vector logs show no TLS, SASL, topic or authorisation failure.

## 1.5 Prove Vector -> Kafka before touching Argo

Use the Confluent portal and the Vector logs together. Do **not** make a new
production consumer group merely to inspect a record.

1. In Vector logs/metrics, capture the successful Kafka sink delivery for the
   run marker.
2. In the Confluent portal, confirm producer activity and a record on the
   approved topic at the same time.
3. Verify the record is the bounded/redacted envelope, not the raw log.
4. Record its timestamp and, if permitted, partition/offset in private
   evidence notes.

If Kafka rejects the record, fix the worker producer identity/topic ACL/TLS
boundary here. Do not start debugging the EventSource until this gate is green.

## Worker exit record

Capture: worker context, namespace, rendered image/reference decisions, Alloy
and Vector rollout output, controlled marker, Vector/Kafka evidence, and proof
that the synthetic token was absent downstream. Then proceed to management.
