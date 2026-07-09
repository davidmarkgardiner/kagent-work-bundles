# Proxmox Smart-Triage Specialist Capacity Fix - 2026-07-09

## Verdict

```text
single_node_pin=addressed
memory_request_limit_ratio=improved
worker_capacity=still_tight
```

## Finding

The smart-triage specialists were previously configured with:

```text
nodeSelector: kubernetes.io/hostname={{SINGLE_WORKER_NODE}}
requests: cpu=1m, memory=16Mi
limits: cpu=250m, memory=256Mi
```

That pinned all specialists to one worker and allowed a 16x memory request to
limit ratio.

## Change Applied

Patched the durable kagent `Agent` CRs, not only the generated Deployments:

```text
Agent.spec.declarative.deployment.nodeSelector removed
Agent.spec.declarative.deployment.resources.requests.cpu=1m
Agent.spec.declarative.deployment.resources.requests.memory=32Mi
Agent.spec.declarative.deployment.resources.limits.memory=256Mi
```

`128Mi` and then `64Mi` memory requests were attempted first, but current
worker capacity could not schedule the full specialist set during rollout.
`32Mi` is the highest request that restored the full specialist fleet in this
dev cluster during this run.

## Verification

All smart-triage specialist Deployments reported:

```text
readyReplicas=1
replicas=1
nodeSelector={}
requests={"cpu":"1m","memory":"32Mi"}
limits={"cpu":"250m","memory":"256Mi"}
```

This improves the memory ratio from 16x to 8x and removes the hard single-node
pin. It does not fully solve sustained-load capacity. A production-ready fix
still needs either more worker headroom, stricter per-agent concurrency, or a
larger request such as `64Mi` or `128Mi` after capacity is added.
