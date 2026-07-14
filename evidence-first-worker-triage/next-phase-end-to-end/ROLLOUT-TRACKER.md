# Rollout Tracker

One line per phase and per onboarded namespace. Update as you go. A phase is not
`done` until every marker in its file is `yes`.

## Phase status

| Phase | State | Evidence file(s) | Notes |
|---|---|---|---|
| 0 — re-prove P0 defect fixes (GATE) | pending | `../evidence/phase0-reprove-*.md` | redaction + correlation; blocks Phase 1 |
| 1 — smoke tests (logs + events) | pending | `../evidence/phase1-*.md` | |
| 2 — Alloy/Vector verified config | pending | `../evidence/phase2-*.md` | |
| 3 — Argo -> GitLab ticket backend | pending | `../evidence/phase3-*.md` | |
| 4 — payload proof + efficiency | pending | `../evidence/phase4-*.md` | |
| 5 — live backend workflow | pending | `../evidence/phase5-*.md` | |
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
