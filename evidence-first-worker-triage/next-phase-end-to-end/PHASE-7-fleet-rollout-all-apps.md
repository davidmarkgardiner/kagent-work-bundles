# Phase 7 — Bake in every application on the cluster

**Goal:** onboard the remaining applications on the cluster, one controlled step
at a time, until every app's incidents flow through the proven path to a
correctly-routed, idempotent triage ticket.

## Why

Phases 1–6 prove the path, the config, the backend, and specialist routing on a
first namespace. Phase 7 is the disciplined expansion: same recipe, one app per
step, each with its own evidence and green verdict before the next.

## Rule

**No batch onboarding.** One application namespace per step, each following the
Phase 6 recipe. If a step goes amber/red, stop and fix before continuing — do
not expand scope on an amber/red verdict (`../CHECKLIST.md` closeout).

## Prompt

```text
Continue onboarding the cluster's applications one namespace per step using the
Phase 6 recipe: scope collection, confirm the specialist routing, smoke test
real failure modes, prove an idempotent correctly-labelled ticket, prove replay
suppression, record green. Maintain a running inventory of onboarded vs pending
namespaces in ROLLOUT-TRACKER.md. For each new app, name the specialist agent
that owns it; if no specialist exists, route to the generic triage agent and
flag that a specialist is needed. Watch fleet-level health as coverage grows:
Kafka lag, consumer-group age, workflow concurrency, DLQ/quarantine rate, agent
concurrency and model/A2A circuit breaker (DS-10, DS-14). If any fleet metric
degrades, pause onboarding, capture it, and fix before adding the next app. Keep
everything additive, reversible, read-only. Alertmanager stays untouched.
```

## Do (per app, until inventory complete)

1. Apply the Phase 6 recipe to the next namespace.
2. Update `ROLLOUT-TRACKER.md`: onboarded / pending / needs-specialist.
3. Re-check fleet metrics (lag, queue age, concurrency, DLQ rate, circuit
   breaker). Degradation -> pause + fix.
4. Green -> next app.

## Evidence to capture (into `../evidence/`)

- `phase7-<namespace>.md` per app — same content as Phase 6.
- `phase7-fleet-health.md` — running fleet metrics as coverage grows.
- `phase7-inventory.md` — final: every namespace, its specialist, its verdict.

## Done when (whole cluster)

```text
NAMESPACES_ONBOARDED: <count>/<total>
ALL_ROUTED_TO_A_SPECIALIST_OR_FLAGGED: yes
FLEET_METRICS_HEALTHY: yes         # lag/queue/concurrency/DLQ/circuit-breaker
NO_AMBER_RED_LEFT_UNOWNED: yes
ALERTMANAGER_UNCHANGED: yes
EVIDENCE_FIRST_WORKER_TRIAGE_VERDICT: green
OUTPUT_SANITIZED: yes
```
