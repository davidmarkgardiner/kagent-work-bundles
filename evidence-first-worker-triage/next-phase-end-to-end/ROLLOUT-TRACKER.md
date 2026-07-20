# Rollout Tracker

One line per phase and per onboarded namespace. Update as you go. A phase is not
`done` until every marker in its file is `yes`.

## Phase status

| Phase | State | Evidence file(s) | Notes |
|---|---|---|---|
| 0 — re-prove P0 defect fixes (GATE) | green | `../evidence/phase0-reprove-redaction-and-correlation.md` | redaction + correlation reproven; found+fixed a live non-atomic claim race (2 tickets for 1 incident) during re-proof, replaced with resourceVersion CAS + unticketed-claim retry |
| 1 — smoke tests (logs + events) | green | `../evidence/phase1-smoke-tests.md` | log+3 event classes (FailedScheduling/BackOff-imagepull/Unhealthy) proven; OOMKilled documented as real platform boundary (no k8s Event emitted on this cluster); replay suppression proven |
| 2 — Alloy/Vector verified config | amber | `../evidence/phase2-*.md` | read-only/redaction/correlation/efficiency proven; VECTOR_FLEET_GRADE=no — disk buffer tried, broke Kafka delivery, reverted (documented); no HA/PDB/topology-spread attempted (owner: whoever promotes to office; expiry: before fleet rollout) |
| 3 — Argo -> GitLab ticket backend | green | `../evidence/phase3-*.md` | agent read-only tool inventory confirmed (8 read-only tools, no mutation tool); idempotent create/update + retry-after-failure proven; found+fixed a residual duplicate-ticket window (ticket created, claim ConfigMap PATCH-back never confirmed before pod death) — `create-gitlab-issue` now searches for an open issue by fingerprint label before creating, and reuses/appends instead of blind-create; TTL store still ConfigMap-level (named office gap, not a blocker for this proof pass) |
| 4 — payload proof + efficiency | amber | `../evidence/phase4-*.md` | severity+container closed and proven; fingerprint discriminating proven; fingerprint NOT stable under pod churn (dedupe_key keys on literal `.pod`, real defect reproduced: same service+signature, different pod name -> 2 tickets #480/#481) — fix recommended (workload-suffix-stripped key), not applied to avoid risking the already-gated P0-2 correlation fix; owner: next fleet-promotion pass; expiry: before Phase 6/7 |
| 5 — live backend workflow | amber | `../evidence/phase5-*.md` | DLQ/quarantine + replay + bounded concurrency built and proven this pass (2 real bugs found+fixed pre-live-traffic); 19 live tickets across the session; BROKER_OUTAGE_LOSS_ACCOUNTED not attempted against real managed Confluent Cloud without an approved maintenance window (owner: Confluent Cloud project owner; expiry: before fleet rollout) |
| 6 — namespace-by-namespace routing | pending | `../evidence/phase6-*.md` | |
| 7 — fleet rollout, all apps | pending | `../evidence/phase7-*.md` | |

States: `pending` -> `in-progress` -> `green` / `amber` / `red`.

## Namespace onboarding (Phase 6 + 7)

| Namespace | Specialist agent | State | Failure modes tested | Ticket proof | Notes |
|---|---|---|---|---|---|
| external-dns | _(discover)_ | pending | | | first target |
| kyverno | _(discover)_ | pending | | | second target |
| _(next)_ | | pending | | | one at a time |

`needs-specialist` = onboarded but routed to the generic agent; a specialist
agent should be created.

## Fleet health (watch during Phase 7)

| Metric | Baseline | Latest | Threshold | OK? |
|---|---|---|---|---|
| Kafka consumer lag | | | | |
| Consumer-group queue age | | | | |
| Workflow concurrency | | | | |
| DLQ / quarantine rate | | | | |
| Agent concurrency | | | | |
| Model / A2A circuit breaker trips | | | | |

Degradation -> pause onboarding, capture, fix, then resume.
