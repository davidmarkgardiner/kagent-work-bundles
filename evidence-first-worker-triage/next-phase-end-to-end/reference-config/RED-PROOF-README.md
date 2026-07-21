# Red-cluster proof overlay

This is an additive proof on `red`. It deliberately does **not** alter the
existing `monitoring/alloy` deployment or its Confluent event path.

It adds a separate, one-replica Alloy collector with the existing `alloy`
service account, then sends pod logs and Kubernetes events to Vector and the
in-cluster Redpanda broker:

```text
alloy-vector-triage (monitoring)
  -> vector-triage (argo-events)
  -> {{KAFKA_BOOTSTRAP}} / {{KAFKA_TOPIC}}
  -> Argo EventSource + Sensor
  -> 24-hour durable claim -> read-only kagent triage -> GitLab work item
```

No Grafana, Loki, Confluent credential, or write-capable kagent tool is used.
The existing Alloy service account has been verified read-only for pods and
events. Argo calls `k8s-readonly-agent` over A2A and creates a GitLab work item
using the pre-existing `argo-events/gitlab-credentials` secret; no credential is
stored in this overlay.

Vector removes immediate duplicate records in memory. The workflow then creates
an atomic ConfigMap claim keyed by cluster, namespace, service and pod. The
claim expires after 24 hours, so the proven in-window replay creates a no-op
workflow. Fleet work must replace this proof-only claim with a durable TTL
store that handles failure release and expiry races before relying on the same
guarantee at scale.

## Red-cluster apply gates

```bash
kubectl config current-context              # must print red
kubectl kustomize observability/alloy-vector-kafka-triage/red
kubectl apply --dry-run=server -k observability/alloy-vector-kafka-triage/red
```

The final apply belongs in the established GitOps path. Once reconciled, use
the controlled crashing workload only in `agentic-triage-proof`; the collector
is deliberately restricted to that namespace for this first live proof.
