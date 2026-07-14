# Changes applied on top of the red proof

`reference-config/` is now **pre-corrected and apply-ready**, not a verbatim copy
of the red proof. The untouched dated proof still lives at its origin
(`observability/alloy-vector-kafka-triage/red/`). These edits fold the
`PAYLOAD-FIELD-PROOF.md` and `SIGNAL-COVERAGE.md` recommendations into the YAML
so the work agent applies, then proves — no design step in between.

**Not runtime-validated here** (no Vector binary in the packaging environment).
YAML parses clean. The Vector VRL and the Argo templates are validated when you
render + server-side dry-run in Phase 0 / Phase 1 — watch that output; if a VRL
line is rejected, it is one of the edits below.

## `02-vector.yaml`

| Change | Where | Why |
|---|---|---|
| Added `.container` extraction | after `.service` | isolate which container failed (was dropped) |
| Added `.severity` derivation | before `.evidence` | events→critical/warning by reason; logs→critical/error by text. Explicit priority, no re-parsing |
| Added `container`, `severity` to envelope allow-list | `. = { … }` | so both reach Kafka → Argo → agent → ticket |
| Widened **log** regex | `incident_signals` condition | added panic, timeout, refused, denied, oom, killed, segfault, traceback, deadlock, unauthorized/forbidden, 500/502/503/504 |
| Widened **event** reason list | `incident_signals` condition | added Evicted, FailedMount, FailedAttachVolume, FailedCreatePodSandBox, NetworkNotReady, ErrImagePull, ImagePullBackOff, NodeNotReady, Preempted, ProbeWarning, FailedSync, FailedKillPod, FailedCreate |

## `03-argo.yaml`

| Change | Where | Why |
|---|---|---|
| Aligned + widened event reason list | `red-event-triage` Sensor filter | now identical to Vector; fixes the `OOMKilling` drop |
| Added `container`, `severity` to `safe_incident` | `create-gitlab-issue` | ticket carries them |
| Added `container`, `severity` to correlated note | `append-correlated-evidence` | follow-up note carries them |
| Added `severity` to ticket title | `create-gitlab-issue` | priority visible at a glance |

## Still the work agent's job (needs the live cluster)

These edits are **applied but unproven**. The Phase 0 gate
(`../KNOWN-DEFECTS-AND-REPROVE.md`) and Phase 1/4 prove them:

- Every widened log class and event reason actually fires through to a workflow.
- `severity` and `container` arrive populated (not empty/`unknown`).
- No secret leaks; a later `BackOff` appends to one ticket.
- Tune the log regex down if a class proves too noisy — log the exclusion.

## Tuning notes

- The log regex is intentionally broad. If it floods, narrow per app and record
  what was dropped (`SIGNAL-COVERAGE.md` rule: no silent drops).
- `severity` mapping is a starting policy. Adjust the critical/warning reason
  sets to your environment; keep it a single versioned policy (do not fork it
  per namespace).
