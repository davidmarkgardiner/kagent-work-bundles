# PRD: daily cluster-health investigation and SRE summary

## Outcome

Collect cluster evidence frequently enough to produce a trustworthy current
snapshot, but publish at most one cluster-health summary per configured UTC
day. When the deterministic daily summary is unhealthy, Argo invokes one
read-only worker-targeted agent investigation and a separate constrained writer
creates or updates one GitLab SRE issue for the cluster.

## Required behavior

- B1 continues five-minute collection; collection frequency is not ticket or
  agent frequency.
- The alert controller emits one `cluster-health.alert.v1` record for each UTC
  daily slot after the configured time. `investigate` means the deterministic
  gate is active; `healthy` means it is clear.
- Reprocessing the same snapshot/slot has the same event and Workflow identity.
- The Sensor invokes the agent only for `investigate`; healthy daily records
  remain Kafka/observability evidence and do not create a Workflow or issue.
- The agent uses only the approved worker-targeted AKS-MCP path and returns one
  bounded root-cause summary. It has no GitLab credential or mutation tool.
- A fixed GitLab adapter searches by exact stable labels. Zero matches creates
  one issue; one match updates it; multiple matches, pagination ambiguity, API
  error or uncertain response fails closed. It never retries an ambiguous
  create inside the same run and never creates one issue per finding.
- No automatic Kubernetes remediation or automatic issue closure is included.

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| One daily record despite 5-minute snapshots/restarts | Controller unit tests and deterministic slot/event identity |
| Healthy day creates no Workflow/ticket | Sensor filter plus contract fixture |
| Kafka replay creates no duplicate Workflow | Deterministic Workflow name |
| One open issue per cluster | GitLab adapter create/update/multiple-match tests |
| Agent cannot write GitLab or Kubernetes | Tool list, Secret placement and effective RBAC tests |
| No raw log/event fan-out | Alert schema, payload size/redaction tests |
| Workplace portability | Digest-pinned render, server dry-run, produced/consumed Kafka proof and controlled fault receipt |

## Non-goals

- Editing or pushing to Fox's repository.
- Per-event, per-log, per-pod or per-namespace issue creation.
- Automatic remediation, issue closure or suppression of the existing incident
  lane before the calibration/soak decision.
- Committing GitLab tokens, Kafka credentials or private endpoints.

## Rollback

Disable the dedicated Sensor first, then scale the alert bridge to zero and
revoke its Kafka producer ACL. Existing B1/Fox collection can remain
report-only. Disable the writer by removing its externally delivered GitLab
Secret or the writer step. Preserve snapshots, Kafka offsets, Workflow output
and the stable issue-label mapping for review.
