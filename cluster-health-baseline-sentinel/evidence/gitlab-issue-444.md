# GitLab issue #444 — produced end-to-end by the sentinel on RED

URL: https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/444
Created: 2026-07-15T10:30:11.002Z
Labels: automated, cluster-health, triage

---

## Cluster health investigation

| Field | Value |
|-------|-------|
| **Incident key** | 3e3c1299121288e5 |
| **Snapshot** | cluster-health-snapshot-1 |
| **Source** | cluster-health-sentinel |

## Orchestrator verdict

```
BASELINE_CROSSED: node_cpu_commit
SEVERITY: warning
ROOT_LAYER: node-pressure
BLAST_RADIUS: Single-node cluster `homelab-control-plane`. No workload eviction or scheduling failure yet. The high CPU commit is cluster-wide by definition (only node), but no workloads are currently failing as a direct downstream symptom. The restart counts in `workload_stress` are chronic and distributed across many namespaces/kube-system components — not a sudden burst correlated with this commit breach. Treat as independent/background noise unless correlated by time.
EVIDENCE:
- snapshot: node_cpu_commit at 93.7% on sole node `homelab-control-plane` (allocatable 8000m, requested 7497m)
- snapshot: scheduling section healthy — 0 pending pods, 0 failed scheduling messages
- snapshot: no pressure conditions (MemoryPressure, DiskPressure, PIDPressure) reported on node
- snapshot: workload_stress shows 0 oom_killed, 0 crashloop, 0 evicted; restarts are high but chronic and spread across many system namespaces, not a new failure wave
- snapshot: control_plane readyz ok, addons all 56 checked and 0 degraded
- snapshot: storage all 8 PVs bound
- snapshot: ip_capacity unavailable (azure workload identity not configured) — no data, not evidence of health or exhaustion
- snapshot: events in 15-min window only 4 warnings, all `UnexpectedJob` in `kagent` — unrelated to node pressure
DELEGATIONS: none
BREWING_RISKS:
- memory_commit_pct at 52.7% leaves headroom, but CPU commit at 93.7% leaves minimal slack for burstable spikes or new pod scheduling on this single-node cluster
- if any workload requests increase or a new deployment rolls out, scheduling may begin failing or kubelet eviction thresholds may be approached
- chronic high restart counts across system components (kindnet 75, metallb 62, workflow-controller 53, etc.) suggest underlying instability that could amplify if node enters actual pressure
- ip_capacity data unavailable; if cluster later uses Azure CNI/overlay, this blind spot matters
RECOMMENDATION:
1. Review CPU request allocations on `homelab-control-plane` to identify over-requested workloads that can be rightsized downward (GitOps change)
2. Evaluate cluster scaling: single-node topology with 93.7% CPU commit is operationally fragile; plan for node addition or control-plane separation
3. Investigate chronic restart pattern in `kube-system`/`metallb-system`/`argo`/`kyverno` separately via per-namespace triage; do not conflate with this commit breach
4. Fix Azure workload identity configuration so `ip_capacity` collection resumes and future IP exhaustion can be detected
REMEDIATION_MODE: gitops_or_workflow_only
HITL_REQUIRED: yes
```
