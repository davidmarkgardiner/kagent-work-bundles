# Phase 5 — Bake in the real backend workflow, create live value

**Goal:** promote the Phase 3 wiring from proof to the **real backend workflow**
so live GitLab tickets are created for real incidents and produce visible value
— a human opens the ticket and it already contains the triage.

## Why

Phases 1–4 prove each part in isolation. Phase 5 runs them as one standing
workflow against real (still non-production, still one pilot namespace)
incidents, with the durable idempotency store, DLQ, and replay handling live —
the full `../DESIRED-STATE.md` DS-07 through DS-13 backend, not a fixture.

## Prompt

```text
Promote the ticket-creating workflow to the standing management backend for the
pilot namespace. Turn on the durable pieces: schema/cluster validation ->
quarantine to DLQ on bad records -> durable TTL claim -> read-only agent ->
idempotent GitLab ticket. Prove the full backend behaviours: a bad record goes
to DLQ with a counter and is replayable; a claim that fails after agent-return
is released and retried without a duplicate ticket; an in-window replay creates
no new ticket; a stale replay is quarantined. Then let real controlled
incidents flow and show live tickets that a human can act on: each ticket
carries bounded redacted evidence, the agent diagnosis, a workflow link, and
verification commands. Keep bounded workflow concurrency. Alertmanager stays
untouched.
```

## Do

1. Enable validation -> DLQ -> TTL claim -> agent -> ticket as the standing
   workflow (DS-07, DS-09, DS-11).
2. Run the backend drills:
   - bad record -> DLQ + counter + replay runbook (DS-07);
   - in-window replay -> no new ticket; stale replay -> quarantined (DS-12);
   - broker outage/drain + loss accounting (DS-13);
   - bounded workflow concurrency under burst (DS-10).
3. Let controlled real incidents flow; collect the live ticket URLs and confirm
   each is human-actionable.

## Evidence to capture (into `../evidence/`)

- `phase5-live-tickets.md` — real ticket URLs/IDs + their evidence bodies.
- `phase5-backend-drills.md` — DLQ, replay, outage, concurrency proofs.
- `phase5-value.md` — one paragraph: what a human saved because the ticket
  arrived pre-triaged (time-to-context).

## Done when

```text
BACKEND_WORKFLOW_LIVE: yes
DLQ_QUARANTINE_PROVEN: yes
REPLAY_IN_WINDOW_AND_STALE_PROVEN: yes
BROKER_OUTAGE_LOSS_ACCOUNTED: yes
WORKFLOW_CONCURRENCY_BOUNDED: yes
LIVE_TICKET_VALUE_SHOWN: yes
ALERTMANAGER_UNCHANGED: yes
OUTPUT_SANITIZED: yes
```
