# GitLab Ticket: Pilot Evidence-First Worker-to-Management Triage

## Summary

Run a reversible non-production pilot that transports bounded Kubernetes log
and event evidence from one worker cluster to a management-cluster read-only
triage workflow. Do not modify Alertmanager, Grafana alerting, existing proxy
paths or production workloads.

## Scope

```text
worker: Alloy -> Vector -> Kafka
management: Kafka -> Argo -> read-only kagent -> idempotent GitLab ticket
```

## Prerequisites

- Independent critique feedback exists and its required corrections are accepted.
- Stakeholder approves a parallel pilot and data classification/retention.
- One non-production worker namespace is selected.
- Kafka identity/ACL, network path and management TTL store are approved.

## Acceptance criteria

- All DS-01 through DS-16 in `DESIRED-STATE.md` have evidence, or an explicit
  amber/red verdict has named owner and expiry.
- One real controlled log and one Kubernetes warning event produce a bounded,
  redacted evidence package, read-only triage and an idempotent work item.
- Replays create no additional agent run or ticket inside the agreed 24-hour
  window.
- Existing Alertmanager routes remain unchanged.
- Output is public-safe and has no secrets/private endpoints.

## Evidence to attach

- Scoped RBAC and worker/management topology summary.
- Sanitized envelopes, Kafka topic/partition/offset and lag evidence.
- Durable idempotency record before/after replay.
- Argo workflow and read-only agent result.
- Ticket URL/idempotency proof.
- Rollback evidence and final desired-state verdict.
