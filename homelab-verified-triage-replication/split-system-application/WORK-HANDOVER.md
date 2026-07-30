# Work handover: staged, segregated triage

## What to deploy

Apply one tier at a time: `CONFIG_TIER1`, then `CONFIG_TIER2`, then
`CONFIG_TIER3`. Both system and application Alloy/Vector lanes run in every
tier. Tier changes widen only Vector and Argo admission: critical, priority,
then broad-warning review.

## Routing contract

Alloy sets `triage_scope`; Vector writes it as Kafka `scope`. Sensors filter
that field. System log/event Sensors trigger `system-agentic-triage`;
application log/event Sensors trigger `application-agentic-triage`.

The work cluster must provide those two WorkflowTemplates (copy the existing
`red-agentic-triage` template twice, change the name, agent invocation,
semaphore key and rate limit). Keep the same incident parameter contract.

## Gate before every promotion

1. Alloy has no `sending queue is full` errors.
2. Vector Kafka produced-message metric advances.
3. The matching scoped Sensor creates its matching WorkflowTemplate.
4. One controlled smoke reaches the intended agent/ticket path.

Do not promote on pod readiness alone.
