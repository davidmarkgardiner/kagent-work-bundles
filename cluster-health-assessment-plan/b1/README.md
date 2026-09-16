# B1 home-lab cluster health assessment

This is the report-only first build gate from the parent plan. It is deployed
to the platform-owned `cluster-health-system` namespace and watches only the
explicit namespace allowlist in `k8s/config.env`.

It creates no Kafka client, makes no model call, and has no GitHub or GitLab
client. The display score is explanatory only. Deterministic domain rules own
the breach and recovery gate.

## What runs

- `cluster-health-snapshot`: a non-overlapping five-minute CronJob.
- `cluster-health-report-morning`: 07:30 Europe/London on weekdays.
- `cluster-health-report-evening`: 16:30 Europe/London on weekdays.
- `cluster-health-metrics`: a read-only Prometheus endpoint and PodMonitor.
- Immutable snapshot and report ConfigMaps plus one mutable latest pointer.

The namespace adapter is implemented directly against the Kubernetes API using
stable controller identity, collapsed scheduling symptoms, successful Job
exclusion, rolling counter deltas, a Warning-event allowlist, bounded
examples/state, and one advisory namespace hygiene aggregate.

The optional [Fox mesh](../fox-mesh/README.md) now runs the upstream Go monitor
for exactly the same namespace scope as the homelab Alloy/Vector lane. B1 reads
each monitor's state ConfigMap and rekeys active Fox findings to stable workload
and symptom identities. The initial `FOX_MESH_MODE=shadow` setting records
coverage and corroboration without changing domain status or the admission
gate. In the workplace bundle Fox's per-finding publisher is disabled; only
the post-gate alert bridge can reach Kafka.

## Validate and deploy

```bash
python3 -m unittest discover -s work-agent-bundles/cluster-health-assessment-plan/b1 -p 'test_*.py' -v
kubectl kustomize work-agent-bundles/cluster-health-assessment-plan/b1 >/tmp/cluster-health-b1.yaml
kubectl --context red apply --dry-run=server -f /tmp/cluster-health-b1.yaml
kubectl --context red apply -k work-agent-bundles/cluster-health-assessment-plan/b1
```

Start a bounded smoke snapshot without waiting for the next schedule:

```bash
kubectl --context red -n cluster-health-system create job \
  --from=cronjob/cluster-health-snapshot cluster-health-snapshot-smoke
kubectl --context red -n cluster-health-system wait --for=condition=complete \
  job/cluster-health-snapshot-smoke --timeout=240s
kubectl --context red -n cluster-health-system logs job/cluster-health-snapshot-smoke
```

Read the latest pointer, snapshot, and metrics:

```bash
kubectl --context red -n cluster-health-system get configmap cluster-health-latest \
  -o jsonpath='{.data.pointer\.json}' | jq
kubectl --context red -n cluster-health-system get --raw \
  '/api/v1/namespaces/cluster-health-system/services/cluster-health-metrics:8080/proxy/metrics'
```

## Security boundary

The assessor has cluster-scoped read access only to Nodes and `/readyz`.
Namespaced Pod, log, Event, controller, Job, and PVC reads are granted by a
RoleBinding in each watched namespace. It can also get only the named
`fox-autonomous-monitor-state` ConfigMap in those namespaces. It can write only
ConfigMaps in the platform namespace. The metrics service account can only get
ConfigMaps there.

Do not replace those RoleBindings with a cluster-wide namespaced-resource
binding at work. Add approved namespaces explicitly and keep
`WATCH_NAMESPACES` aligned with them.

## Calibration and rollback

The first ten working days remain report-only. Label morning and evening slots,
including false positives and missed/late slots. Gate G1 is not complete until
that set spans a real weekend and has SRE acceptance.

To stop collection without deleting evidence:

```bash
kubectl --context red -n cluster-health-system patch cronjob cluster-health-snapshot \
  --type=merge -p '{"spec":{"suspend":true}}'
kubectl --context red -n cluster-health-system patch cronjob cluster-health-report-morning \
  --type=merge -p '{"spec":{"suspend":true}}'
kubectl --context red -n cluster-health-system patch cronjob cluster-health-report-evening \
  --type=merge -p '{"spec":{"suspend":true}}'
```

Export immutable ConfigMaps before deleting the Kustomize bundle. Deleting the
namespace also deletes all local snapshots and reports.
