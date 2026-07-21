# LGTM Node Auto-Provisioning, Scheduling and Eviction Examples

## Purpose

This sheet focuses on AKS Node Auto-Provisioning (NAP), scheduling and evictions. It complements [LGTM Alert Coverage Baseline](BASELINE.md) and the [AKS Node Auto-Provisioning Platform Guide](../../../docs/platform-kb/aks/node-auto-provisioning.md).

NAP is AKS-managed Karpenter. Application teams make pods schedulable through requests, constraints and disruption budgets; the platform owns NAP, NodePool, AKSNodeClass, quota/subnet guardrails and monitoring. The public KRO template currently keeps NAP disabled, so these are future candidates until a target explicitly enables it.

## Signal ownership

| Signal | Collection/query path |
|---|---|
| Pending workload state | kube-state-metrics -> Mimir/PromQL |
| FailedScheduling, Preempted, Evicted and node events | Alloy Kubernetes Event watch -> Loki/LogQL |
| Read-only event triage evidence | Alloy -> Vector -> Kafka -> Argo |
| NAP/Karpenter decisions | AKS control-plane karpenter-events logs and validated Karpenter metrics |
| Node pressure/capacity | node, kubelet and kube-state-metrics -> Mimir |

Alloy can collect Kubernetes events and logs; it is not itself a scheduler or NAP metric source. Crucially, the Kubernetes Event watch may not capture AKS control-plane Karpenter events. Make that source separately queryable in LGTM.

## Pending and unschedulable pods

~~~promql
# Candidate: CriticalPodPendingTooLong
max by (cluster, namespace, pod) (
  kube_pod_status_phase{
    cluster="{{CLUSTER_NAME}}", namespace="{{NAMESPACE}}", phase="Pending"
  }
) == 1

# Candidate: ClusterPendingPodRatio
# The denominator must exclude completed pods. An unqualified
# kube_pod_status_phase sum counts Succeeded/Failed Job pods, which accumulate
# over time and steadily dilute the ratio until a real pending incident can no
# longer cross the threshold.
sum by (cluster) (kube_pod_status_phase{
  cluster="{{CLUSTER_NAME}}", phase="Pending"
})
/
clamp_min(sum by (cluster) (kube_pod_status_phase{
  cluster="{{CLUSTER_NAME}}", phase=~"Pending|Running|Unknown"
}), 1)
> {{PENDING_POD_RATIO_THRESHOLD}}
~~~

`CriticalPodPendingTooLong` has no threshold of its own: `Pending` is normal for
a few seconds during image pull and scheduling, so the rule is only meaningful
with a `for:` duration attached at rule-provisioning time. Set it from the
platform provisioning SLO — long enough that healthy startup never pages, short
enough to beat the SLO. Without it the rule fires on every pod start.

Use a named tier-1 workload alert in addition to the fleet ratio. A fleet ratio
alone cannot page for one unschedulable critical pod.

The `FailedScheduling` event objective is defined once, as `PodFailedScheduling`
in [Kubernetes events](EXAMPLES-KUBERNETES-EVENTS.md#candidate-logql-alerts).
Deploy it from there and read this sheet for the scheduling interpretation;
do not define a second rule with the same expression under a different name, or
every scheduling failure pages twice.

Preemption is specific to this sheet:

~~~logql
# Candidate: PreemptedWorkloadEvents
sum by (cluster, obj_namespace) (
  count_over_time({cluster="{{CLUSTER_NAME}}", event_type="Warning",
    event_reason="Preempted"}[10m])
) > 0
~~~

## Evictions and pressure

~~~promql
# Candidate: NodeMemoryPressure
kube_node_status_condition{
  cluster="{{CLUSTER_NAME}}", condition="MemoryPressure", status="true"
} == 1

# Candidate: NodeDiskPressure
kube_node_status_condition{
  cluster="{{CLUSTER_NAME}}", condition="DiskPressure", status="true"
} == 1
~~~

The eviction event objective is likewise defined once, as `PodEvicted` in
[Kubernetes events](EXAMPLES-KUBERNETES-EVENTS.md#candidate-logql-alerts). The
node-pressure conditions above are this sheet's contribution: they are the
correlating evidence, not a second eviction alert.

Eviction is not proof that memory was the cause. The runbook must correlate event message, node condition, resource usage, pod requests/limits and PDB status.

## NAP/Karpenter objectives

Confirm the enabled version's actual metrics and event schema before writing rules. Candidate objectives are:

- a pending tier-1 pod has a matching failed provisioning attempt;
- a required NodePool/capacity class reaches its limit;
- a NodeClaim exceeds the platform provisioning SLO;
- consolidation/disruption affects a protected workload or exceeds an agreed rate;
- subnet, VM-family quota or identity failure blocks capacity creation.

The platform guide identifies AKSControlPlane records with Category equal to karpenter-events as the NAP event source. Feed/link that source separately; do not assume Alloy's Event API watcher collects it.

## Alloy event evidence

~~~alloy
loki.source.kubernetes_events "events" {
  namespaces = []
  job_name   = "kubernetes-events"
  log_format = "json"
  forward_to = [loki.process.parse_event.receiver] // required; config fails to load without it
}
~~~

Use the full collection contract and the agreed label model from
[Kubernetes events](EXAMPLES-KUBERNETES-EVENTS.md#required-alloy-event-shape) —
this fragment is the same pipeline, not a second one.

Parse type, reason, involved-object namespace/name; add static cluster/environment labels; forward a redacted first occurrence to Loki and the separate Vector/Kafka/Argo evidence path. Keep an explicit Warning-event allow-list including FailedScheduling, Evicted, Preempted, NodeNotReady, FailedMount and FailedCreatePodSandBox.

## Proof scenarios

1. A lower-environment unschedulable fixture proves FailedScheduling in Loki, alerting and Kafka/Argo triage.
2. A safe capacity-demand fixture proves NAP provision evidence and eventual scheduling, or the intended failure route.
3. An approved disruption test with disposable PDB-protected workloads proves eviction/disruption visibility and recovery.
4. A non-production/synthetic capacity failure proves quota/subnet handling without exhausting production capacity.

Record defined, scoped, routed and proven for every objective. Keep remediation human/GitOps-controlled.
