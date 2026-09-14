# Daily cluster-health verification

Date: 2026-09-14
Cluster: `red` local lab

## Result

Workflow `cluster-certification-qxv9l` finished `Succeeded` with all nine nodes complete. It ran from 10:12:36Z to 10:14:36Z. The schedule remains suspended and the cluster-health agent was returned to zero replicas after the run.

The report recorded four of six checks as passed:

- The control plane passed.
- The only node was Ready.
- DNS resolved both Kubernetes service names and had two ready endpoints.
- All 23 persistent volume claims were Bound.
- The add-on check failed because `kagent/mcpg-data-contract-skill-gitref-spike-agent` was 0 of 1 Ready.
- The baseline check was critical but unchanged. It reported the same degraded add-on, one long-pending workload, and three warnings against a median of one.

The read-only agent traced those signals to one cause. The spike agent's init container tries to clone a Git branch that no longer exists. The pod was in `Init:CrashLoopBackOff` with 2,174 restarts over 7 days and 17 hours. The agent classified the scheduling and warning signals as symptoms of that chronic fault, not separate incidents.

The agent also tried the knowledge agent. That call returned `429 insufficient_quota`, so the previous-incident check remained unknown. This is a real dependency failure and must appear in the daily report.

## Safety receipt

- `cluster-certification-config` remained `report-mode: log-only`.
- The ticket step logged `log-only mode: no ticket filed`.
- The agent returned `REMEDIATION_MODE: gitops_or_workflow_only` and `HITL_REQUIRED: yes`.
- No remediation was attempted.
- `dice-daily-cluster-health` remains `suspend: true` with no scheduled runs.
- `cluster-health-orchestrator` was scaled back to zero replicas after the manual run.

## Failures retained

Workflow `cluster-certification-5hk4f` exposed a stale Argo condition. A comma-separated failed-check value was inserted into the old `when` string and caused an expression error. The template now uses Argo expression syntax.

Workflow `cluster-certification-fdmvk` reached the agent call while its Deployment was scaled to zero. The controller returned no diagnosis text, and the Workflow failed closed. The successful run started only after the agent had one Ready replica.

## Remaining gate

Do not enable the 07:00 schedule yet. First choose the report destination, review baseline thresholds, and prove the agent availability method. Send failed or changed reports into the common incident contract only after the daily report has a stable fingerprint and a specific target-bound action can enter the existing approval flow.
