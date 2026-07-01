# Work Agent Prompt: Argo Workflow Retention Cleanup

You are working on a real management Kubernetes cluster that may have hundreds
of thousands of Argo `Workflow` custom resources. The goal is to reduce etcd and
API-server pressure safely, then put controls in place so this does not recur.

Do not print secrets, private hostnames, internal URLs, subscription IDs, tenant
IDs, or token values. Record resource names, namespaces, labels, and sanitized
evidence only.

## Objective

Clean up excessive Argo workflows and install a sustainable retention model:

1. Verify the target management cluster.
2. Measure workflow volume by namespace, phase, age, and owner/source.
3. Identify and pause/fix the source if workflows are still being created.
4. Dry-run cleanup commands before deleting anything.
5. Delete old completed workflows in controlled batches.
6. Classify stale active workflows separately before terminating or deleting.
7. Add Argo-native defaults for TTL, pod GC, and max runtime.
8. Add a daily cleanup backstop CronJob through the approved GitOps path.
9. Add or confirm Grafana/Prometheus visibility for workflow growth and cleanup
   success/failure.
10. Produce a concise evidence and rollback report.

## Required Inputs

Ask for these only if they cannot be discovered safely:

```text
{{MGMT_KUBE_CONTEXT}}
{{ARGO_WORKFLOWS_NAMESPACE}}
{{ARGO_EVENTS_NAMESPACE}}
{{GITOPS_REPO_OR_APP_PATH}}
{{RETENTION_SUCCESS_HOURS}}
{{RETENTION_FAILURE_HOURS}}
{{RETENTION_ERROR_HOURS}}
{{MAX_WORKFLOW_RUNTIME_HOURS}}
{{DAILY_CLEANUP_SCHEDULE}}
{{WORKFLOW_COUNT_WARNING_THRESHOLD}}
{{WORKFLOW_COUNT_CRITICAL_THRESHOLD}}
```

Use these defaults unless the platform owner gives different values:

```text
RETENTION_SUCCESS_HOURS=24
RETENTION_FAILURE_HOURS=72
RETENTION_ERROR_HOURS=72
MAX_WORKFLOW_RUNTIME_HOURS=8
DAILY_CLEANUP_SCHEDULE=02:30 local cluster time
```

## Hard Safety Rules

- Do not run blanket deletion without a dry-run first.
- Do not delete active `Running`, `Pending`, or `Suspended` workflows until they
  have been classified.
- Do not use `--force` unless normal deletion fails because of stuck finalizers
  and the platform owner explicitly approves it.
- Do not delete retained workflows labelled for audit, production evidence, or
  incident investigation.
- Do not pause a `CronWorkflow`, `Sensor`, or event source until you understand
  the production impact and have a rollback command.
- Prefer GitOps for permanent manifests and config changes.
- Keep all evidence sanitized.

## Phase 1: Preflight

Run:

```bash
kubectl config current-context
kubectl api-resources | grep -E 'workflows|cronworkflows'
kubectl get workflows.argoproj.io -A --no-headers | wc -l
kubectl get cronworkflows.argoproj.io -A
kubectl get sensors.argoproj.io -A 2>/dev/null || true
kubectl get pods -A | grep -E 'argo|workflow' || true
```

Return:

```text
PREFLIGHT: passed_or_blocked
CLUSTER_CONTEXT:
ARGO_WORKFLOWS_NAMESPACE:
ARGO_EVENTS_NAMESPACE:
ARGO_CLI_AVAILABLE: yes_or_no
WORKFLOW_TOTAL:
CRONWORKFLOW_TOTAL:
SENSOR_TOTAL:
IMMEDIATE_RISK:
NEXT_ACTION:
```

## Phase 2: Inventory And Source Analysis

Count workflows by namespace and phase:

```bash
kubectl get workflows.argoproj.io -A -o json \
  | jq -r '.items[] | [.metadata.namespace, (.status.phase // "Unknown")] | @tsv' \
  | sort \
  | uniq -c \
  | sort -nr
```

Find source/owner patterns:

```bash
kubectl get workflows.argoproj.io -A -o json \
  | jq -r '.items[] |
      [
        .metadata.namespace,
        .metadata.name,
        (.status.phase // "Unknown"),
        (.metadata.labels["workflows.argoproj.io/creator"] // "unknown"),
        (.metadata.labels["workflows.argoproj.io/workflow-template"] // "unknown"),
        (.metadata.ownerReferences[0].kind // "none"),
        (.metadata.ownerReferences[0].name // "none"),
        .metadata.creationTimestamp
      ] | @tsv' \
  | sort \
  | head -300
```

Return:

```text
INVENTORY:
TOTAL_WORKFLOWS:
COUNTS_BY_NAMESPACE_AND_PHASE:
TOP_SUSPECT_NAMESPACES:
TOP_SUSPECT_CREATORS:
TOP_SUSPECT_CRONWORKFLOWS:
TOP_SUSPECT_SENSORS:
COUNT_STILL_INCREASING: yes_no_unknown
RECOMMENDED_SOURCE_PAUSE:
```

## Phase 3: Pause Or Fix The Source

If workflow count is still increasing, identify the source and propose the least
disruptive pause.

For a `CronWorkflow`, prefer:

```bash
kubectl patch cronworkflow -n {{NAMESPACE}} {{NAME}} \
  --type merge \
  -p '{"spec":{"suspend":true}}'
```

For an Argo Events sensor, document the event path and production impact before
scaling or disabling anything.

Return:

```text
SOURCE_CONTROL:
SOURCE_IDENTIFIED: yes_no
SOURCE_TYPE:
SOURCE_NAMESPACE:
SOURCE_NAME:
PAUSE_ACTION:
ROLLBACK_ACTION:
APPROVAL_REQUIRED:
ACTION_TAKEN:
```

## Phase 4: Completed Workflow Cleanup

Prefer Argo CLI if available.

Start conservative:

```bash
argo delete -A --completed --older 14d --dry-run --query-chunk-size 500
argo delete -A --completed --older 14d --query-chunk-size 500
```

Then, if API-server and etcd health remain acceptable:

```bash
argo delete -A --completed --older 7d --dry-run --query-chunk-size 500
argo delete -A --completed --older 7d --query-chunk-size 500

argo delete -A --completed --older 3d --dry-run --query-chunk-size 500
argo delete -A --completed --older 3d --query-chunk-size 500
```

Do not jump straight to `1d` until failed/error evidence retention has been
agreed.

After each batch, return:

```text
CLEANUP_BATCH:
COMMAND:
DRY_RUN_RESULT:
DELETION_RESULT:
WORKFLOW_TOTAL_BEFORE:
WORKFLOW_TOTAL_AFTER:
API_SERVER_HEALTH:
ETCD_HEALTH:
ARGO_CONTROLLER_HEALTH:
ERRORS:
NEXT_BATCH_RECOMMENDATION:
```

## Phase 5: Stale Active Workflow Handling

Classify active workflows before any action:

```bash
kubectl get workflows.argoproj.io -A -o json \
  | jq -r '.items[] |
      select((.status.phase // "Unknown") | IN("Running","Pending","Suspended")) |
      [.metadata.namespace, .metadata.name, (.status.phase // "Unknown"), .metadata.creationTimestamp] |
      @tsv'
```

Recommend one of:

- leave alone
- investigate scheduling/RBAC/resource issue
- terminate then delete after grace period
- exclude because it is intentionally suspended
- escalate for owner decision

Return:

```text
STALE_ACTIVE_WORKFLOWS:
RUNNING_OLDER_THAN_MAX_RUNTIME:
PENDING_OLDER_THAN_MAX_QUEUE_TIME:
SUSPENDED:
RECOMMENDED_ACTIONS:
APPROVAL_REQUIRED:
ACTION_TAKEN:
```

## Phase 6: Permanent Retention Defaults

Find the installed Argo Workflows deployment path and controller config source.
Prefer the approved GitOps repo/app path.

Propose this default unless environment policy differs:

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

Validate with the appropriate mechanism:

```bash
helm template ...
kubectl kustomize ...
kubectl apply --dry-run=server -f ...
```

Return:

```text
RETENTION_DEFAULTS:
CONFIG_SOURCE:
CHANGE_PATH:
VALIDATION_COMMAND:
VALIDATION_RESULT:
ROLLBACK:
READY_FOR_GITOPS_PR_OR_APPLY:
```

## Phase 7: Daily Backstop CronJob

Create or propose a daily cleanup CronJob using the approved GitOps path.

Minimum behaviour:

```bash
argo delete -A --completed --older 3d --query-chunk-size 500
```

The job must:

- use least-privilege RBAC
- log counts before and after
- not print secrets
- have resource requests/limits
- have successful/failed job history limits
- run out of hours
- fail if the expected cluster/namespace markers are not present

Return:

```text
DAILY_BACKSTOP:
MANIFEST_PATH:
SCHEDULE:
RBAC_SCOPE:
VALIDATION_COMMAND:
VALIDATION_RESULT:
ROLLBACK:
```

## Phase 8: Monitoring And Evidence

Confirm or propose dashboards/alerts for:

- workflow count by namespace
- workflow count by phase
- workflow creation rate
- workflows older than retention
- cleanup CronJob success/failure
- cleanup deleted count
- Argo controller health
- API server and etcd health

Return the final report:

```text
FINAL_REPORT:
CLUSTER_CONTEXT:
INITIAL_WORKFLOW_TOTAL:
FINAL_WORKFLOW_TOTAL:
SOURCE_OF_GROWTH:
SOURCE_PAUSED_OR_FIXED:
CLEANUP_PERFORMED:
RETENTION_DEFAULTS_ADDED:
DAILY_BACKSTOP_ADDED:
MONITORING_ADDED_OR_PROPOSED:
RISKS_REMAINING:
ROLLBACK_COMMANDS:
FOLLOW_UP_TICKETS:
```

Stop and ask for operator approval before any destructive action that falls
outside this prompt.
