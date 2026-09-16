# Single-cluster manager-and-worker receipt

Run ID: `cluster-health-single-cluster-20260915`  
Executed: 2026-09-15, final receipt at 21:00 UTC  
Kubernetes context: `red`  
Mode: one API server, separate worker and manager namespaces, report-only, external writes disabled

## Active topology

- `cluster-health-system` owns collection, immutable snapshots, local morning/evening reports, and the latest-snapshot publisher.
- `agent-health-system` owns authenticated intake, PostgreSQL state, deterministic evidence assessment, and the suspended summary ledger.
- The publisher endpoint is `https://cluster-health-intake.agent-health-system.svc:8443/v1/snapshots`.
- The intake Service is `ClusterIP`; no NodePort or cross-cluster route is active.
- Worker and manager keep separate ServiceAccounts, Secrets and storage. There is no shared filesystem.

The earlier `kind-agent-cage-health` proof environment was quiesced after cutover: intake and PostgreSQL desired replicas are zero, both cage CronJobs are suspended, and its PVC was retained for recovery evidence. It is not an active second manager.

## Live proof

Worker sequence 38 crossed the namespace boundary with an identical SHA-256 checksum, produced a deterministic assessment with zero tools and model disabled, and created exactly one local summary key:

```text
cluster-health/homelab-worker-red  status=open  revision=1
```

An identical summary reconciliation returned `action=unchanged`; the ledger remained one row at revision 1. A later final convergence moved worker and manager to sequence 41 with matching checksum `sha256:b6e8beb23d0dba0ef19776f618979be67dbd04328b1b695e3aa72c2776365b33`.

Permission checks on the same API server returned:

- publisher can get worker-state ConfigMaps: `yes`;
- publisher can get manager Secrets: `no`;
- publisher can list manager pods: `no`;
- intake, assessor and summary reconciler service-account token mounts: `false`.

Both active manager pods were Ready with zero restarts at the final receipt. The summary reconciler remained suspended and `external_writes=0`.

## Packaging resolution

The first single-cluster cutover found that the checked-in intake image was absent from the amd64 `red` node. A temporary source-running pod proved the topology while image delivery was repaired. Its first compiler attempt exceeded 512 MiB memory, and a later pod exceeded the temporary 256 MiB module cache. These are retained as failure evidence, not as the final runtime.

The checked-in multi-stage Dockerfile was then cross-built for `linux/amd64` and imported into the node-local containerd store as `cluster-health-intake:b2-20260915`. The imported OCI index digest was `sha256:2edf581168e68f77e7074cfa63d7c7725f6e3a43c900d84939b9a2dc89cd5d7a`; the running container image ID was `sha256:f0687c4179ced1c6d39f3d09434f9c740a4f37f751f9ee90198fed43316811a6`.

The Deployment was restored to the compiled `/usr/local/bin/intake` entrypoint, `128Mi` memory limit, and TLS-only volume mount. The temporary source ConfigMap and containerd loader pod were deleted. A fresh rollout after that deletion became Ready with zero restarts, reported `x86_64`, and had no `/src` mount. Worker sequence 41 was then newly accepted (`duplicate: false`) through that binary and its deterministic assessment was also newly accepted with model disabled and zero tool calls.

Node-local loading closes the homelab runtime defect; it is not the workplace image-distribution design. Before GitOps promotion, publish this compiled image to the approved registry and pin the immutable registry digest in the environment overlay.

## Proof boundary

This topology intentionally pretends that one cluster is both manager and worker. Namespace RBAC and credential separation are real; API-server, network and physical failure-domain separation are not. Moving to two clusters later changes the publisher endpoint and component placement, not the snapshot, authentication, storage or assessment contracts.
