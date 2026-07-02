# Argo Workflow Retention Cleanup

## TL;DR

Use this bundle when a management cluster has accumulated a very large number
of Argo `Workflow` custom resources and etcd/API-server health is being
affected.

The recommended approach is:

1. Stop or pause the source creating excessive workflows.
2. Inventory workflows by namespace, phase, age, and owner.
3. Bulk-delete old completed workflows in controlled batches.
4. Add Argo-native retention defaults using `ttlStrategy`, `podGC`, and
   `activeDeadlineSeconds`.
5. Add a daily cleanup CronJob as a backstop, not as the primary control.
6. Add monitoring so workflow count growth is visible before etcd is affected.

Do not start by deleting every workflow in one command. A cluster with hundreds
of thousands of Workflow CRs is already under pressure, so cleanup should be
chunked, observable, and reversible at the source.

## Why This Is Needed

Argo `Workflow` objects store workflow execution state in Kubernetes. Keeping
hundreds of thousands of completed or stale workflow objects in the API server
increases pressure on etcd, the API server, Argo controllers, watches, and
cluster backup/restore operations.

Workflow history should not live indefinitely as live Kubernetes CRs. If
long-term evidence is required, use Argo Workflow Archive, object storage,
GitLab/Azure DevOps evidence, ServiceNow records, or another approved evidence
store.

## Immediate Recovery Plan

### 1. Confirm The Cluster And Scale

Run this first against the affected management cluster:

```bash
kubectl config current-context
kubectl get workflows.argoproj.io -A --no-headers | wc -l
kubectl get cronworkflows.argoproj.io -A
kubectl get sensors.argoproj.io -A 2>/dev/null || true
```

Summarise workflow counts by namespace and phase:

```bash
kubectl get workflows.argoproj.io -A -o json \
  | jq -r '.items[] | [.metadata.namespace, (.status.phase // "Unknown")] | @tsv' \
  | sort \
  | uniq -c \
  | sort -nr
```

Find the busiest workflow creators:

```bash
kubectl get workflows.argoproj.io -A -o json \
  | jq -r '.items[] |
      [
        .metadata.namespace,
        .metadata.name,
        (.status.phase // "Unknown"),
        (.metadata.labels["workflows.argoproj.io/creator"] // "unknown"),
        (.metadata.ownerReferences[0].kind // "none"),
        (.metadata.ownerReferences[0].name // "none"),
        .metadata.creationTimestamp
      ] | @tsv' \
  | head -200
```

### 2. Pause The Source If It Is Still Creating Workflows

Do this before large deletion if counts are still rising.

Likely sources:

- `CronWorkflow` schedules.
- Argo Events `Sensor` triggers.
- Alertmanager/Grafana/Kafka event loops.
- Retry loops in `WorkflowTemplate` or agent workflows.
- A controller or script repeatedly submitting workflows.

Safe first actions are usually:

```bash
kubectl patch cronworkflow -n {{NAMESPACE}} {{NAME}} \
  --type merge \
  -p '{"spec":{"suspend":true}}'
```

or scale/pause the specific event source/sensor only after confirming the
production impact:

```bash
kubectl scale deployment -n {{ARGO_EVENTS_NAMESPACE}} {{SENSOR_DEPLOYMENT}} --replicas=0
```

Record every pause action and rollback command.

### 3. Delete Completed Workflows In Batches

Prefer the Argo CLI when available:

```bash
kubectl config current-context

argo delete -A --completed --older 14d --dry-run --query-chunk-size 500
argo delete -A --completed --older 14d --query-chunk-size 500

argo delete -A --completed --older 7d --dry-run --query-chunk-size 500
argo delete -A --completed --older 7d --query-chunk-size 500

argo delete -A --completed --older 3d --dry-run --query-chunk-size 500
argo delete -A --completed --older 3d --query-chunk-size 500
```

If `kubectl config current-context` is empty, the Argo CLI will fail with:

```text
Error: invalid configuration: no configuration has been provided, try setting KUBERNETES_MASTER environment variable
```

Either select the target context first:

```bash
kubectl config use-context {{MGMT_KUBE_CONTEXT}}
```

or pass the context explicitly on every command:

```bash
argo --context {{MGMT_KUBE_CONTEXT}} delete -A --completed --older 14d --dry-run --query-chunk-size 500
argo --context {{MGMT_KUBE_CONTEXT}} delete -A --completed --older 14d --query-chunk-size 500
```

Tighten the retention gradually. Watch API server, etcd, Argo controller, and
namespace workflow counts between each pass.

If Argo CLI access is not available, use Kubernetes deletion carefully by
namespace and label/field scope. Do not run a blanket `kubectl delete wf -A
--all` unless the platform owner has explicitly approved that loss of evidence.

Validation note: this command shape was verified with Argo CLI `v3.7.1` against
the local `kind-argo-workflow` context using two labelled test workflows. The
dry-run selected only the labelled terminal workflows, and the non-dry-run
deleted them. The same test also confirmed that `--completed` includes terminal
`Error` workflows, so keep the staged retention policy if failed/error workflow
evidence must be retained longer than successful runs.

### 3a. Large Backlog Fast Path

For very large backlogs, for example `{{WORKFLOW_COUNT}}` in the hundreds of
thousands, `argo delete --completed` can be too slow because it still deletes
workflows one at a time. `--query-chunk-size` chunks the list request, not the
delete operations.

Use the bundled batched deleter when the Argo CLI path is too slow:

```bash
cd work-agent-bundles/argo-workflow-retention-cleanup

./scripts/delete-completed-workflows-batched.sh \
  --context {{MGMT_KUBE_CONTEXT}} \
  --older 14d \
  --batch-size 200 \
  --parallel 4 \
  --dry-run

./scripts/delete-completed-workflows-batched.sh \
  --context {{MGMT_KUBE_CONTEXT}} \
  --older 14d \
  --batch-size 200 \
  --parallel 4 \
  --yes
```

Then tighten gradually:

```bash
./scripts/delete-completed-workflows-batched.sh --context {{MGMT_KUBE_CONTEXT}} --older 7d --batch-size 200 --parallel 4 --dry-run
./scripts/delete-completed-workflows-batched.sh --context {{MGMT_KUBE_CONTEXT}} --older 7d --batch-size 200 --parallel 4 --yes

./scripts/delete-completed-workflows-batched.sh --context {{MGMT_KUBE_CONTEXT}} --older 3d --batch-size 200 --parallel 4 --dry-run
./scripts/delete-completed-workflows-batched.sh --context {{MGMT_KUBE_CONTEXT}} --older 3d --batch-size 200 --parallel 4 --yes
```

The script:

- lists candidate workflows once per pass using `kubectl get workflows -o json`;
- filters by age and terminal phase with `jq`;
- deletes many workflow names per `kubectl delete` request;
- limits concurrent delete requests with `--parallel`;
- requires `--dry-run` or explicit `--yes`.

Start with `--batch-size 100 --parallel 2` on a pressured management cluster.
Increase to `--batch-size 200 --parallel 4` only if API server, etcd, and Argo
controller health remain stable. Avoid high parallelism; deleting 250,000 CRs is
still API-server and etcd work even when client-side round trips are reduced.

If failed/error workflows need longer retention, clean successful workflows
first:

```bash
./scripts/delete-completed-workflows-batched.sh \
  --context {{MGMT_KUBE_CONTEXT}} \
  --older 1d \
  --phases Succeeded \
  --dry-run
```

### 4. Treat Stale Running Or Idle Workflows Separately

Do not blindly delete active workflows just because they are old.

Classify them first:

```bash
kubectl get workflows.argoproj.io -A -o json \
  | jq -r '.items[] |
      select((.status.phase // "Unknown") | IN("Running","Pending","Suspended")) |
      [.metadata.namespace, .metadata.name, (.status.phase // "Unknown"), .metadata.creationTimestamp] |
      @tsv'
```

Recommended policy:

| Phase | Action |
|---|---|
| `Succeeded` | Delete after 24 hours unless labelled for retention |
| `Failed` / `Error` | Keep 72 hours for investigation, then delete |
| `Running` older than approved max runtime | Terminate or stop first, then delete after grace period |
| `Pending` older than approved max queue time | Investigate scheduling/RBAC/resource issue, then terminate/delete if abandoned |
| `Suspended` | Exclude unless clearly disposable |

## Permanent Fix

Set controller-level defaults so new workflows clean themselves up.

Example `workflow-controller-configmap` default:

```yaml
workflowDefaults: |
  spec:
    activeDeadlineSeconds: 28800
    ttlStrategy:
      secondsAfterSuccess: 86400
      secondsAfterFailure: 259200
      secondsAfterError: 259200
    podGC:
      strategy: OnPodCompletion
```

Suggested defaults:

- `activeDeadlineSeconds: 28800`: cap runtime at 8 hours unless a workflow
  explicitly needs longer.
- `secondsAfterSuccess: 86400`: keep successful workflows for 1 day.
- `secondsAfterFailure: 259200`: keep failed workflows for 3 days.
- `secondsAfterError: 259200`: keep errored workflows for 3 days.
- `podGC.strategy: OnPodCompletion`: remove workflow pods once completed.

If specific workflows need longer retention, label them and document the
exception. Do not let the default become indefinite retention.

## Daily Backstop Cleanup

Use a Kubernetes `CronJob` as a backstop. It should be boring, scoped, and
observable.

Recommended job behaviour:

- Runs once daily out of hours.
- Deletes completed workflows older than the approved retention.
- Uses small query chunks.
- Excludes explicitly retained workflows where possible.
- Emits counts before and after cleanup.
- Fails closed if it cannot identify the cluster context or namespace.
- Does not print secrets.

Example command:

```bash
argo delete -A --completed --older 3d --query-chunk-size 500
```

For stale `Running` / `Pending` workflows, use a separate job or manual
approval path. That path should terminate first, then delete after a grace
period.

## Monitoring And Alerts

Add Grafana/Prometheus visibility for:

- total workflow count by namespace
- workflow count by phase
- workflows older than retention by namespace
- workflow creation rate
- Argo controller queue/reconcile health
- Kubernetes API server and etcd health
- cleanup job success/failure
- cleanup job deleted count

Alert before the cluster reaches emergency scale, for example:

- warning: more than `{{WORKFLOW_COUNT_WARNING_THRESHOLD}}` workflows
- critical: more than `{{WORKFLOW_COUNT_CRITICAL_THRESHOLD}}` workflows
- critical: cleanup job failed for two consecutive runs
- critical: workflow count continues increasing after source pause

## Definition Of Done

The work is complete when:

- The affected management cluster is correctly identified.
- The source of excessive workflow creation is identified and paused or fixed.
- Workflow counts by namespace and phase are captured before cleanup.
- Completed workflows are deleted in controlled batches.
- Stale active workflows are separately classified and handled.
- Argo controller defaults enforce TTL, pod GC, and max runtime for new runs.
- A daily cleanup backstop exists through GitOps or the approved deployment path.
- Monitoring and alerting exist for workflow growth and cleanup failures.
- Evidence is captured without secrets or private endpoint values.
- Rollback instructions are documented for every pause or config change.

## References

- Argo `ttlStrategy` and `podGC` field reference:
  `https://argo-workflows.readthedocs.io/en/latest/fields/`
- Argo default workflow specs:
  `https://argo-workflows.readthedocs.io/en/latest/default-workflow-specs/`
- Argo cost optimisation guidance:
  `https://argo-workflows.readthedocs.io/en/latest/cost-optimisation/`
- Argo `delete` CLI:
  `https://argo-workflows.readthedocs.io/en/latest/cli/argo_delete/`
- Argo Workflow Archive:
  `https://argo-workflows.readthedocs.io/en/latest/workflow-archive/`
