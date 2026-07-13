# Stakeholder Decision: Evidence-First Triage Pilot

## Decision

For the agentic triage/CHAIR system, the LGTM/Alertmanager integration is not
fit for purpose as the primary source of actionable log and Kubernetes-event
evidence. After roughly six months of repeated implementation attempts and
cross-team engagement, it has not reliably delivered the evidence package the
system needs. The required specialist capacity and support have not been
available to close that gap.

Stop investing in that dependency for this use case. Pilot the direct evidence
path instead:

```text
Alloy -> Vector -> Kafka -> Argo -> read-only triage -> GitLab
```

Keep Alertmanager for human-facing metric paging and Grafana/Loki for search
and dashboards. This is not a claim that LGTM is unfit for every observability
purpose; it is a scope-specific decision that it is not the right primary
transport for actionable agent evidence in this system.

## Rationale

The failed route asks Alertmanager/LGTM to supply all alert, metric, log and
event context to the agent. In practice it requires custom webhook/proxy and
payload-conversion code, continual integration work, and often a second lookup
to reconstruct the evidence after the alert fires. Despite repeated work, that
has not become a dependable operational path.

The evidence-first path carries a redacted, bounded source package while its
pod/cluster/workload identity is still available. Vector controls immediate
local noise; management will own durable idempotency and ticketing once the
critique controls are implemented.

## Guardrails

- One non-production worker namespace first.
- No change to existing human paging.
- Read-only triage only.
- Explicit data classification, Kafka ACLs, retention, concurrency and
  rollback decisions.
- Expand only after critique corrections and desired-state evidence are green.
