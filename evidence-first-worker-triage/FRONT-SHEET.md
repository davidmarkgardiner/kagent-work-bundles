# Front Sheet: Evidence-First Worker Triage

## One-line outcome

Prove that a worker cluster can forward a redacted, bounded log or Kubernetes
event evidence package to a management cluster, where one read-only triage run
and one GitLab work item are created per durable incident fingerprint.

## Design position

- **Alloy:** source collection and Kubernetes metadata at the worker.
- **Vector:** worker-local redaction, normalisation, correlation, caps and
  short-lived burst suppression.
- **Kafka:** authenticated cross-cluster handoff, buffering and replay.
- **Management Argo:** schema validation, durable TTL idempotency, concurrency
  control and workflow audit.
- **kagent:** read-only diagnosis using the attached evidence package.
- **GitLab:** idempotent ticket creation/update.

Grafana/Loki may be follow-up evidence tools. Alertmanager may continue to page
humans for metrics, but neither is a dependency for this log/event agent path.

## Current state

| Item | State |
|---|---|
| Single-cluster log route | Proven on `red` |
| Single-cluster Kubernetes `BackOff` route | Proven on `red` |
| 24-hour replay suppression | Proven on `red` |
| Worker-to-management transport | Design to validate |
| Office durable TTL store | Decision required |
| Office data classification/retention | Decision required |
| Office rollout | Blocked pending owner acceptance of critique corrections |

## Non-negotiable boundaries

- No direct agent mutation or remediation.
- No cluster credentials, secrets, hostnames or private IPs in the bundle.
- No broad all-namespace rollout as a first proof.
- No change to existing Alertmanager routes for this pilot.
- No ticket without the durable idempotency claim succeeding first.

## First pilot

One non-production worker namespace, one approved log signature, one approved
Kubernetes warning event, one management consumer, and one read-only agent.
The rollback is to disable the new producer/consumer route; existing human
alerting remains untouched.
