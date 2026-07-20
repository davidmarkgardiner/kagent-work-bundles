# Phase 2 — Alloy: applied config, read-only proof

Live config as applied to `red` (`monitoring/alloy-vector-triage-red-config`,
`monitoring/alloy-vector-triage` Deployment) — identical to
`../reference-config/01-alloy.yaml` (`kubectl apply --dry-run=server`
reported `unchanged` when re-applied, confirming the live object already
matched the pre-corrected reference before any Phase 1/2 work began).

## Read-only proof (DS-02)

Service account `alloy` (namespace `monitoring`) is bound to two
ClusterRoles, both `get`/`list`/`watch` only — no write verb anywhere:

```yaml
# clusterrole/alloy
- apiGroups: [""]
  resources: [nodes, nodes/proxy, nodes/metrics, services, endpoints, pods, pods/log]
  verbs: [get, list, watch]
- apiGroups: [networking.k8s.io]
  resources: [ingresses]
  verbs: [get, list, watch]
- nonResourceURLs: ["/metrics", "/metrics/cadvisor"]
  verbs: [get]
# clusterrole/alloy-k8s-events
- apiGroups: [""]
  resources: [events]
  verbs: [get, list, watch]
- apiGroups: [""]
  resources: [namespaces, pods, nodes]
  verbs: [get, list, watch]
```

Checked with `kubectl get clusterrole alloy -o jsonpath='{.rules}'` and the
`alloy-k8s-events` equivalent, plus a full scan of every `ClusterRoleBinding`/
`RoleBinding` in the cluster for the `alloy` subject — only the two bindings
above exist, both to read-only roles.

## Namespace scope (DS-02)

The collector is additive and scoped to the pilot namespace only, at the
`discovery.relabel` stage (pod logs) and at the source config (k8s events):

```river
discovery.relabel "pod_logs" {
  targets = discovery.kubernetes.pods.targets
  rule { source_labels = ["__meta_kubernetes_namespace"]; target_label = "namespace" }
  rule { source_labels = ["__meta_kubernetes_pod_name"]; target_label = "pod" }
  rule { source_labels = ["__meta_kubernetes_pod_container_name"]; target_label = "container" }
  rule { source_labels = ["__meta_kubernetes_pod_label_app_kubernetes_io_name"]; target_label = "service" }
  rule { source_labels = ["__meta_kubernetes_namespace"]; regex = "agentic-triage-proof"; action = "keep" }
}
loki.source.kubernetes_events "events" {
  namespaces = ["agentic-triage-proof"]
  ...
}
```

`discovery.kubernetes "pods"` itself watches all pods cluster-wide (that is
how `nodes`/`pods`/`pods/log` get/list/watch is used), but the `keep` rule
drops everything outside `agentic-triage-proof` before any log line leaves
Alloy — this is the same reason the original 2026-07-13 proof gives for
scoping it narrow: unscoped log tailing exceeded the collector's memory
budget on this cluster (`RED-PROOF-README.md`). This is a **deliberate,
already-documented boundary** carried forward unchanged, not a new finding.

This Deployment does **not** touch the pre-existing, separately-managed
`monitoring/alloy` Deployment/Confluent event path (`alloy-confluent` secret,
`alloy-k8s-events`/`k8s-warning-events` chain) — confirmed by name, labels
(`app.kubernetes.io/part-of: alloy-vector-kafka-triage` on the additive
collector vs. the pre-existing `alloy` deployment carrying no such label),
and separate ServiceAccount RBAC review above.

## Discovery-latency finding (operational, not a correctness defect)

Documented already in `phase1-smoke-tests.md`: pod-log discovery latency for
brand-new, non-restarting pods was inconsistent during this session — from
~7s to ~3 minutes in different observed runs, with no isolated root cause.
Any future onboarding onto this pattern should account for this when
choosing fixture/test-pod lifetimes, and Phase 6/7 (namespace-by-namespace
rollout) should re-check it under real application pod lifecycles rather than
short-lived synthetic fixtures, since a genuinely short-lived pod (a failed
init container, a crash within the first couple of seconds) could in the
worst observed case exit before Alloy attaches.
