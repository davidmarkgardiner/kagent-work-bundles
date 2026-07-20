# Phase 1 — Smoke tests: prove logs AND events

**Goal:** both an application **log** error and a Kubernetes **event** (Warning)
independently reach the Argo workflow through the same path. Not one, both.

## Why this first

The happy path proves "a pod fired and something arrived." That is one path.
The design (`../DESIRED-STATE.md` DS-15) needs the **log path** and the **event
path** proven separately, because Alloy collects pod logs while Kubernetes
events come from a different source and are easy to silently drop.

## Prompt

```text
Run controlled smoke tests that separately prove the log path and the event
path end to end: pod -> Alloy -> Vector -> Kafka -> Argo. Use the bundled
fixtures, do not hand-edit production workloads. For each source, capture the
Kafka offset the record landed on, the sanitized envelope, and the Argo
workflow that consumed it. Confirm event classes cover at least
FailedScheduling, OOMKilled/OOMKilling, and image pull / BackOff. Prove a
duplicate of the same incident within the dedupe window creates no second
workflow. Leave Alertmanager untouched.

Note: on the proof cluster, `OOMKilled`/`OOMKilling` is never emitted as a
Kubernetes Event by this kubelet (verified absent even when the OOM kill
itself is confirmed via container exit code) — a platform boundary, not a
pipeline defect. `Unhealthy` was substituted as the third proven class; see
`evidence/phase1-smoke-tests.md` for the full analysis.
```

## Do

```bash
# From the parent bundle folder:
bash scripts/verify-healthy.sh   --values /secure/pilot-values.env
bash scripts/simulate-failures.sh --values /secure/pilot-values.env
# ... capture evidence, then:
bash scripts/simulate-failures.sh --values /secure/pilot-values.env --cleanup
```

For each of the two sources (log, event):
1. Trigger the fixture in the pilot namespace only.
2. Read the Kafka topic and record the **partition/offset** the envelope hit.
3. Confirm the Argo workflow that consumed that offset ran and carried the
   evidence.
4. Fire the same fixture again inside the dedupe window; confirm **no** second
   workflow / claim / ticket.

## Coverage completeness (see `SIGNAL-COVERAGE.md`)

Do not test only the reasons already in the allow-list — that proves the filter
matches itself, not that nothing is missed. `SIGNAL-COVERAGE.md` lists the log
classes and event reasons that *should* fire but are dropped today (both the
narrow log regex and the narrow event list, plus a Vector↔Argo mismatch on
`OOMKilling`). Widen both filters and prove each class reaches a workflow before
freezing this namespace as the golden path.

## Field completeness (see `PAYLOAD-FIELD-PROOF.md`)

Proving "a record arrived" is not enough. For each fired log and event, prove
the envelope carries every field the agent needs to isolate the issue without
digging: cluster, message type (`signal_kind`), the actual message
(`representative_log_lines`), what the error is (`reason`/`event_summary`), pod,
service, namespace, timestamp, and the two fields the red proof was missing —
`severity` and `container`. `PAYLOAD-FIELD-PROOF.md` has the captured evidence
(tickets #430 log / #431 event), the field table, and the two gaps to close.

## Evidence to capture (into `../evidence/`)

- `phase1-log-path.md` — fixture, envelope (sanitized), topic/partition/offset,
  Argo workflow name, dedupe-on-replay proof.
- `phase1-event-path.md` — same, for each event class tested.
- Consumer-group lag before/after, showing the records were actually consumed.

## Done when

```text
LOG_EVIDENCE_PATH_PROVEN: yes
EVENT_EVIDENCE_PATH_PROVEN: yes
EVENT_CLASSES_COVERED: FailedScheduling,BackOff(ImagePull),Unhealthy   # >= 3; OOMKilled substituted, see note above
REPLAY_SUPPRESSED: yes
ALERTMANAGER_UNCHANGED: yes
OUTPUT_SANITIZED: yes
```
