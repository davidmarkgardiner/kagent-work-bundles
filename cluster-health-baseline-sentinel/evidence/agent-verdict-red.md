# Real orchestrator verdict — RED, 2026-07-15

Produced end-to-end by the deployed chain: collector CronJob detected
`node_cpu_commit` at 93.6%, POSTed a breach transition, the sensor submitted a
workflow, the workflow inlined the snapshot into the agent's prompt, the agent
returned this. Verbatim from the workflow's node outputs.

This is the artifact that justifies the design. Read the `EVIDENCE` block
closely — specifically the line tagged `tool:`.

```text
BASELINE_CROSSED: node_cpu_commit
SEVERITY: warning
ROOT_LAYER: node-pressure
BLAST_RADIUS: Single-node cluster `homelab-control-plane`. No workload eviction
or scheduling failure yet. The high CPU commit is cluster-wide by definition
(only node), but no workloads are currently failing as a direct downstream
symptom. The restart counts in `workload_stress` are chronic and distributed
across many namespaces/kube-system components — not a sudden burst correlated
with this commit breach. Treat as independent/background noise unless correlated
by time.
EVIDENCE:
- snapshot: node_cpu_commit at 93.7% on sole node `homelab-control-plane`
  (allocatable 8000m, requested 7497m)
- snapshot: scheduling section healthy — 0 pending pods, 0 failed scheduling messages
- snapshot: no pressure conditions (MemoryPressure, DiskPressure, PIDPressure) on node
- snapshot: workload_stress shows 0 oom_killed, 0 crashloop, 0 evicted; restarts
  are high but chronic and spread across many system namespaces, not a new failure wave
- snapshot: control_plane readyz ok, addons all 56 checked and 0 degraded
- snapshot: storage all 8 PVs bound
- snapshot: ip_capacity unavailable (azure workload identity not configured) —
  no data, not evidence of health or exhaustion
- snapshot: events in 15-min window only 4 warnings, all `UnexpectedJob` in
  `kagent` — unrelated to node pressure
DELEGATIONS: none
BREWING_RISKS:
- memory_commit_pct at 52.7% leaves headroom, but CPU commit at 93.7% leaves
  minimal slack for burstable spikes or new pod scheduling on this single-node cluster
- if a new workload requests significant CPU it will fail to schedule
RECOMMENDATION:
1. Review CPU requests on homelab-control-plane and right-size or remove
   unnecessary workloads
2. Plan to add worker nodes or migrate to multi-node to relieve the bottleneck
3. Monitor for pending pods; if any appear, the cluster is at hard scheduling capacity
REMEDIATION_MODE: gitops_or_workflow_only
HITL_REQUIRED: yes
```

## Why this output is the proof, not just a demo

**1. It caught our misleading data.** From an earlier run of the same chain:

> `tool: kube-system pods all Running; restarts are historical (all marked "47d ago"),
> suggesting a past event or chronic pressure rather than an acute spike`

The snapshot reports **cumulative** restart counts — kindnet 75, metallb 62,
workflow-controller 53. Those look like a crisis and mean nothing without a
delta. Unprompted, the agent used its read-only tools to check the ages, found
they were ~47 days old, and discounted them as chronic. A separate investigation
later root-caused that exact wave to a kind node restart (64 containers,
including etcd, all exiting 255 at the same second) — **confirming the agent's
read was correct.**

It could only afford that judgement because it wasn't spending its tool budget
re-deriving the basics. That is the "hand it the snapshot" design paying off.

**2. It handled missing data correctly.**

> `snapshot: ip_capacity unavailable (azure workload identity not configured) —
> no data, not evidence of health or exhaustion`

Exactly the semantics the collector's `status: ok|unavailable` contract is meant
to carry. Absence of evidence was not read as evidence of absence.

**3. It declined to delegate.** `DELEGATIONS: none`. The snapshot answered the
question; there was no gap worth a sub-agent call. An agent that delegates for
show would have burned tokens to add nothing.

**4. It separated correlation from causation.** The restart counts were the most
alarming numbers on the page, and it explicitly refused to attribute them to the
breach: *"Treat as independent/background noise unless correlated by time."*

## Caveat on the numbers

`93.7%` here versus `93.6%` elsewhere: the collector and the agent sampled
seconds apart on a live cluster. Both are correct for their instant.

The `events in 15-min window only 4 warnings` line is **from before the timestamp
fix** — at the time, `window_minutes: 15` was not actually windowing (see
`../LESSONS.md` §2). The exclusion of Kyverno noise was real; the window was not.
