# Single-cluster manager and worker topology

Use this overlay while only one Kubernetes cluster exists. It treats two namespaces on the same API server as separate logical roles:

- `cluster-health-system`: worker collection, local reports, and the latest-snapshot publisher.
- `agent-health-system`: manager intake, PostgreSQL state, evidence assessment, and the suspended summary writer.

The publisher uses the intake's internal ClusterIP DNS name. No NodePort, cross-cluster filesystem, or externally routed health endpoint is required. Authentication, cluster/generation binding, bounded snapshots, separate ServiceAccounts, and separate database credentials remain in place so a later split into two clusters changes placement and networking rather than the contract.

Render with:

```bash
kubectl kustomize work-agent-bundles/cluster-health-assessment-plan/single-cluster
```

Create the TLS, HMAC, PostgreSQL, CA, and internal-client Secrets through the approved runtime secret path. The TLS certificate must include `cluster-health-intake.agent-health-system.svc`.

The lab manifest deliberately uses `imagePullPolicy: Never`, so every eligible homelab node must already contain the compiled image for its architecture. Build the current amd64 artifact with:

```bash
docker buildx build --platform linux/amd64 --load \
  --tag cluster-health-intake:b2-20260915 \
  work-agent-bundles/cluster-health-assessment-plan/b2/intake
```

Load that image into the node runtime using the cluster's approved local-image mechanism before applying the overlay. Do not compile or run Go source in the intake pod. Replace the lab image reference with an immutable approved-registry digest before permanent GitOps delivery.

The B4 reconciler remains suspended and has no GitLab client. The normal assessor remains deterministic unless an approved model route and runtime Secret are deliberately enabled.
