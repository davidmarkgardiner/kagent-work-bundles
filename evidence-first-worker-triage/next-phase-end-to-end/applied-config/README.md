# Applied config — delta vs `../reference-config/`

These are the manifests actually applied to the `red` cluster for gate 0 and
phases 1-5, kept here for traceability. They are **not** a redesign of
`reference-config/02-vector.yaml` / `03-argo.yaml` — same sources, same Kafka
topic, same 4-step workflow (claim → diagnose → create-issue → append). No
secrets or endpoints are hardcoded here beyond what `reference-config/` already
references (`secretKeyRef`s only).

## `02-vector-with-metrics.yaml`

Identical to `reference-config/02-vector.yaml` (same VRL, same filters, same
Kafka sink) plus one **additive, read-only** change: an `internal_metrics`
source and a `prometheus_exporter` sink on port 9598. This is required to
satisfy `KNOWN-DEFECTS-AND-REPROVE.md` requirement 3 ("a rejected family shows
a visible drop/quarantine metric, not a silent near-miss") — without it there
was no way to observe `incident_signals`' discard count. Proven:
`vector_component_discarded_events_total{component_id="incident_signals",intentional="true"}`
is live and non-zero. Does not touch the data path.

## `03-argo-augmented.yaml`

Two deltas vs `reference-config/03-argo.yaml`, both explained inline as
comments in the file itself:

1. **EventSource omitted.** The live `red-telemetry-triage-kafka` EventSource
   already targets the real, discovered Confluent Cloud environment (topic
   `k8s-events`, SASL via the `confluent-credentials` secret) per the parent
   bundle's "Confluent Kafka is already reachable" instruction.
   `reference-config`'s EventSource block still targets the local-Redpanda
   proof value; applying it verbatim would have regressed a working real
   integration. Sensors and WorkflowTemplate were applied; EventSource was
   left untouched.
2. **`claim-24h-window` rewritten for correctness, `create-gitlab-issue` /
   `append-correlated-evidence` rendered as a markdown contract instead of a
   raw JSON block.** See `../evidence/phase0-reprove-redaction-and-correlation.md`
   for why: the original delete-then-create refresh path is a non-atomic
   TOCTOU race that reproduced the exact P0-2 defect (two tickets for one
   incident) during this regression run. Replaced with a
   resourceVersion-guarded compare-and-swap, plus explicit handling for a
   claim that is held-but-never-ticketed (prior agent/ticket-step failure) so
   it is retried instead of silently stuck for the rest of its 24h TTL.

## Phase 5 additions (new, not in `reference-config/` at all)

3. **`validate-schema` step + `process-incident` sub-template** — a DLQ/
   quarantine gate that did not exist at proof level. Rejects unsupported
   `schema_version`, unexpected `cluster`, and stale (>24h old)
   `observed_timestamp` records to a labeled, replayable ConfigMap instead of
   processing them as fresh incidents. See
   `../evidence/phase5-backend-drills.md` for two real bugs found and fixed
   while building this (a `$$`-uniqueness bug, and an Argo template-reference
   bug when chaining `when` across a possibly-skipped step) — both before
   this was ever exposed to live Sensor-triggered traffic.
4. **`spec.synchronization.semaphore`** on the WorkflowTemplate, backed by
   `04-workflow-concurrency.yaml` — bounds concurrent `red-agentic-triage`
   instances to 5, scoped to this template only (does not touch the shared
   cluster-wide `workflow-controller-configmap`). Proven with an 8-incident
   concurrent burst: exactly 5 ran at a time, the rest queued cleanly, all 8
   eventually ticketed.
