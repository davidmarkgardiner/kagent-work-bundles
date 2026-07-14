# Phase 2 — Show the tested, most-efficient Alloy + Vector config

**Goal:** produce the reference Alloy + Vector configuration you actually tested
and verified in Phase 1, with the reasoning for why each control is on and why
it is efficient. This is the "how we built it well" artifact.

## Why

Phase 1 proved the path works. Phase 2 captures *how it should be configured* so
it can be repeated on every future namespace/cluster without rediscovering the
tuning. Efficiency = only collect what triage needs, redact/bound at the source,
and never pay Kafka/agent cost for obvious local noise.

## Prompt

```text
Document the exact Alloy and Vector configuration proven in Phase 1. For Alloy:
show the read-only node-local log collection, the namespace scope, and that it
carries no write/RBAC beyond read. For Vector: show worker-local aggregation
(HA/PDB/topology spread), disk buffer + delivery policy + buffer-full loss
metric, the redaction/PII pack, the single normalised envelope schema, the
fingerprint key (workload+signature), and the immediate-burst suppression. For
each setting, state what it costs if removed. Prove efficiency with numbers:
records in vs records produced to Kafka, bytes per envelope, redaction/drop
counts. Keep secrets as references only.
```

## Starting point

The proven baseline is in `reference-config/` (see `PROVENANCE.md`):
`01-alloy.yaml` and `02-vector.yaml`. Document the **applied** config against
that baseline — note any office deviation.

## Do

1. Pull the applied Alloy fragment and Vector config from the cluster (the
   live objects, not the template) and sanitize them.
2. Annotate each block against the parent controls:
   - Alloy: read-only + namespace scope (DS-02).
   - Vector: HA/PDB/placement + disk buffer + buffer-full loss metric (DS-03),
     fingerprint (DS-04), redaction/caps (DS-05), envelope normalisation,
     burst suppression (DS-15).
3. Measure efficiency: input event rate vs Kafka produce rate, envelope size,
   drop/redaction counters.

## Evidence to capture (into `../evidence/`)

- `phase2-alloy-config.md` — sanitized applied config + read-only proof.
- `phase2-vector-config.md` — sanitized applied config + per-control rationale.
- `phase2-efficiency.md` — in/out record ratio, bytes/envelope, drop counters,
  and a one-line statement of what was dropped and why (no silent truncation).

## Done when

```text
WORKER_ALLOY_READ_ONLY: yes
WORKER_VECTOR_REDACTION: yes
WORKER_VECTOR_CORRELATION: yes
VECTOR_FLEET_GRADE: yes            # HA/PDB/buffer/loss-metric shown
ENVELOPE_EFFICIENCY_MEASURED: yes  # numbers, not adjectives
OUTPUT_SANITIZED: yes
```
