# Pilot Checklist

## Before any office change

- [ ] Read `FABLE-FEEDBACK-RESPONSE.md` and record accepted corrections.
- [ ] Obtain stakeholder approval for a parallel, non-production pilot.
- [ ] Select exactly one worker cluster and one namespace.
- [ ] Classify permitted evidence and set redaction/retention limits.
- [ ] Approve Kafka transport identity, topic ACLs and network path.
- [ ] Select the management TTL/idempotency store and ticket idempotency key.
- [ ] Define workload+signature and node-scoped fingerprint classes.
- [ ] Approve redaction pack/scanner, prompt/ticket scrub and schema/DLQ/replay policy.
- [ ] Confirm the agent has only read-only tools.
- [ ] Confirm current Alertmanager routes are out of scope and capture baseline.

## Build and prove

- [ ] Deploy scoped Alloy collection on the worker.
- [ ] Deploy worker-local Vector aggregation with disk buffer and schema checks.
- [ ] Prove HA/PDB/placement, delivery policy and buffer-full loss metric.
- [ ] Prove a redacted log evidence envelope reaches Kafka.
- [ ] Prove a redacted Kubernetes warning-event envelope reaches Kafka.
- [ ] Prove management validation/quarantine and durable claim occur before agent call.
- [ ] Kill agent/ticket step and prove claim failure releases/retries safely.
- [ ] Prove one read-only A2A triage response and one GitLab ticket per source.
- [ ] Prove ticket post-create retry and long-lived incident update behaviour.
- [ ] Test in-window, group-name/oldest and stale replay behaviour.
- [ ] Run burst, broker-outage and A2A circuit-breaker drills.
- [ ] Capture lag, queue age, redaction/drop/quarantine and agent concurrency data.
- [ ] Disable the route and prove the rollback leaves human alerting unchanged.

## Closeout

- [ ] Complete `evidence/EVIDENCE-TEMPLATE.md`.
- [ ] Compare evidence against `DESIRED-STATE.md`.
- [ ] Publish green/amber/red verdict and named next owner.
- [ ] Do not expand cluster scope on an amber/red verdict without approval.
