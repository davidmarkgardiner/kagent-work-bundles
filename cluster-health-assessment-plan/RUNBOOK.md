# Cluster-health lab runbook

## Normal operation

The active one-cluster topology keeps worker collection in `cluster-health-system` and manager state in `agent-health-system` on the same API server. The worker produces five-minute snapshots and 07:30/16:30 weekday reports in `Europe/London`. The independent publisher sends only the latest snapshot to the manager namespace over authenticated ClusterIP HTTPS. The manager retains attempts separately from the latest complete snapshot and prepares an evidence-only handoff. External summary delivery stays disabled.

Check the worker:

```bash
kubectl --context {{WORKER_CONTEXT}} -n cluster-health-system get cronjobs,pods
kubectl --context {{WORKER_CONTEXT}} -n cluster-health-system get configmap cluster-health-latest -o jsonpath='{.data.pointer\.json}'
```

Check the manager namespace:

```bash
kubectl --context {{WORKER_CONTEXT}} -n agent-health-system get pods,cronjobs
kubectl --context {{WORKER_CONTEXT}} -n agent-health-system logs -l app.kubernetes.io/name=cluster-health-assessor --tail=20
```

Treat a missing or partial current snapshot as missing evidence, never as health. The local worker report remains the fallback during manager-namespace or service failure.

## Intake image delivery

The intake pod runs the compiled `/usr/local/bin/intake` binary. It must not mount source or compile code at startup. The homelab manifest uses `imagePullPolicy: Never`; cross-build the artifact for the node architecture and load it into every eligible node before rollout:

```bash
docker buildx build --platform linux/amd64 --load \
  --tag cluster-health-intake:b2-20260915 \
  work-agent-bundles/cluster-health-assessment-plan/b2/intake
```

Use the cluster runtime's approved image-loading mechanism. Confirm the deployed pod uses only the `tls` mount, has no command override, and runs the compiled entrypoint:

```bash
kubectl --context {{WORKER_CONTEXT}} -n agent-health-system get deployment cluster-health-intake -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl --context {{WORKER_CONTEXT}} -n agent-health-system exec deployment/cluster-health-intake -- readlink /proc/1/exe
```

For workplace GitOps, publish the multi-stage build output to the approved registry and replace the lab tag with an immutable registry digest. Node-local loading is only a homelab bootstrap path.

## Stop and recover

Suspend the summary reconciler first. It is shipped suspended and must remain so until an authorised sandbox writer trial. To stop cross-cluster traffic without stopping collection, suspend only `cluster-health-publisher`. Do not suspend `cluster-health-snapshot`.

After intake recovery or database restore, publish the latest complete worker snapshot once, confirm the stored generation/sequence/checksum, then run the assessor once. Identical publications and assessments must report `duplicate: true`. Keep external delivery disabled until mappings and budgets have been reconciled.

## Workplace lift-and-shift gates

Map placeholders privately, render through the existing GitOps path, and repeat RBAC, TLS/authentication, wrong-identity, partial-state, outage, restore, and dedupe drills. Then complete real elapsed calibration and a separately authorised GitLab sandbox trial during staffed hours. Production triage remains off until named SRE ownership and stop-write recovery are accepted.
