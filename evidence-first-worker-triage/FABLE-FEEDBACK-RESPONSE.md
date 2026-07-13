# Fable Feedback Response and Bundle Gate

Source review: `docs/observability/FABLE-WORKER-TO-MANAGEMENT-TRIAGE-FEEDBACK.md`.

## Position

Fable’s verdict is **sound with material gaps**. The red proof remains valid
for its narrow happy path; it is not a fleet implementation. This bundle
defines the corrections required before office implementation and does not
claim that they already exist.

```text
CRITIQUE_FEEDBACK_REVIEWED: yes
FLEET_CORRECTIONS_DEFINED: yes
OFFICE_IMPLEMENTATION_AUTHORIZED: no_pending_owner_acceptance
```

## Must-have corrections

| Finding | Required correction | Desired-state gate |
|---|---|---|
| Pod-name/no-signature fingerprint | Workload+normalised-signature key; node-scoped class; pod-churn and distinct-signature tests | DS-04 |
| Claim-then-fail lockout | Atomic TTL store, retry/release or failed state, unresolved-claim alert | DS-09 |
| Post-Kafka loss unknown | At-least-once Kafka→EventBus→Sensor contract and burst test | DS-10 |
| One-regex redaction | Versioned secrets/PII rule pack plus sampled scanner | DS-05 |
| Tainted log evidence | File/artifact data handoff, prompt delimiters and ticket scrub | DS-06 |
| Ticket retry/daily duplication | Ticket idempotency, update-open-ticket and atomic expiry takeover | DS-11 |
| v2/v3 drift/silent drops | Version migration contract, quarantine/DLQ and replay runbook | DS-07, DS-08 |
| Proof-grade Vector | HA/PDB/spread, disk buffer, explicit delivery settings and loss metric | DS-03 |
| Replay after group change | Timestamp-skew policy and replay drill | DS-12 |
| Metric page + evidence ticket co-occur | Ticket correlation labels and operating note | DS-15 |

## Required owner decisions

```text
CRITIQUE_CORRECTIONS_ACCEPTED: yes|no
DURABLE_TTL_STORE: {{APPROVED_BACKEND}}
WORKER_TO_MANAGEMENT_IDENTITY: {{APPROVED_MTLS_OR_SASL_MODEL}}
DATA_CLASSIFICATION_AND_RETENTION: {{APPROVED_POLICY_REFERENCE}}
```

Priority lanes, results topics, dashboards-as-code and Grafana/Loki mirrors are
valuable later work, not first-pilot prerequisites.
