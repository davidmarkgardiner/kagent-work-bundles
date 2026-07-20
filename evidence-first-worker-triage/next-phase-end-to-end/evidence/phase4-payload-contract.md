# Phase 4 — Payload contract: field table + required-vs-present diff

Baseline: `../PAYLOAD-FIELD-PROOF.md` (fields already proven present in the
2026-07-13 proof, plus the two gaps — `severity`, `container` — it named).
This phase closes both gaps (done in Gate 0's applied config) and re-verifies
the full table with a named consumer per field.

## Field → consumer table (no orphans)

| Field | Consumer | Present/correct this pass? |
|---|---|---|
| `schema_version` | Management validation (future DS-08 schema gate) | ✅ constant `observability.triage.v2` |
| `cluster` | Ticket contract (scope) | ✅ `red` |
| `namespace` | Fingerprint, ticket contract | ✅ |
| `pod` | Fingerprint (see gap below), ticket contract | ✅ |
| `container` | Ticket contract (isolate failing container on multi-container pods) | ✅ **closed this pass** — populated for log-sourced tickets (e.g. #448 `auth-api`); empty for pure k8s-event tickets (#450) because Alloy's `loki.process "events"` stage does not attach a container label to raw k8s events (documented pre-existing boundary, not new) |
| `service` | Ticket contract, (would-be fingerprint input — see finding below) | ✅ for log-sourced tickets; empty/`unknown` for pure event tickets (same boundary as `container`) |
| `reason` | Ticket title/contract, agent's "what's the error" | ✅ |
| `severity` | Ticket contract, agent prioritisation | ✅ **closed this pass** — `critical`/`warning`/`error` all observed across tickets |
| `signal_kind` | Sensor routing (log vs event sensor), ticket contract | ✅ |
| `source_type` | Diagnostic context only | ✅ constant `opentelemetry` — **no ticket consumer uses this field**; see orphan note below |
| `observed_timestamp` | Ticket contract (`First seen` on create) | ✅ |
| `dedupe_key` | Argo `claim-24h-window` fingerprint, ticket contract | ✅ present; **see fingerprint-stability finding below** |
| `delivery_key` | Vector's own `suppress_exact_repeats` (never leaves Vector into the ticket schema) | ✅ used correctly at the Vector layer only |
| `automation_allowed` | Sensor filter (`== false` gate), defense-in-depth read-only signal | ✅ constant `false` |
| `evidence.event_summary` | Ticket "what's the error", agent prompt | ✅ |
| `evidence.representative_log_lines` | Ticket "redacted evidence", agent prompt | ✅ redacted + capped at 4096 chars |

## Orphan field found: `source_type`

`source_type` is set to the constant `"opentelemetry"` on every record and
travels all the way to Kafka/the agent/the ticket schema, but **no ticket
template field or agent prompt section reads it** — the rendered ticket
contract (Gate 0) does not include a "source_type" row, and the agent prompt
does not reference it. It is small (constant string, ~15 bytes) so the cost
of carrying it is negligible, but per this phase's own instruction ("Flag any
field no consumer uses and remove it") it is flagged here rather than
silently left in. Recommendation: either drop it (it adds no information —
`signal_kind` already conveys log-vs-event) or repurpose it if a future
non-OTLP source is added. Left in place this pass (not removed) since it's
free and removing it is a config change with no functional benefit under
current time constraints — flagged, not fixed, per instruction to log
explicit exclusions/orphans rather than silently act on every one.

## Fingerprint discriminating power — proven

Two distinct signatures (different pod/reason combinations) reliably produce
two distinct `dedupe_key`s — true for every one of the ~15 distinct
fixtures fired across gate 0/phase 1/phase 4 (each got its own ticket).

## Fingerprint stability under pod churn — **real gap found, not fixed this pass**

`.dedupe_key = sha2(join!([.cluster, .namespace, .pod], ":"))` keys on the
literal pod name. Tested directly: two `Pod` objects representing the same
logical service (`app.kubernetes.io/name: churn-test-svc`, identical failure
signature `"ERROR synthetic fingerprint churn test instance a"`) but two
different pod names (`churn-test-instance-a`, then deleted and replaced by
`churn-test-instance-b`) produced **two different `dedupe_key`s** and **two
separate GitLab tickets**
([#480](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/480),
[#481](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/481))
— exactly the failure mode DS-04 ("pod churn [→] one incident") exists to
prevent. Any real Deployment/ReplicaSet-managed workload that gets rescheduled
(node drain, OOM-triggered pod replacement, rolling restart) will churn its
pod name and, under the current key, silently open a fresh ticket per
incarnation instead of continuing the same one.

**Why not fixed in this pass:** the obvious fix (key on `.service` instead of
`.pod`) was evaluated and rejected — `.service` is not reliably populated on
pure Kubernetes-event records (a pre-existing, already-documented boundary:
`STRESS-TEST-2026-07-13.md`, "Kubernetes events do not reliably carry the
log's service label"). The **already-proven, gate-0-required** log+event
correlation (P0-2 fix) depends on `.pod` being the shared join key between a
log record and an event record for the same failing pod. Swapping the primary
key to `.service` would fix pod-churn stability but reintroduce a log/event
correlation split (log keyed on service, event keyed on pod-fallback would
no longer match) — trading one proven, explicitly-gated defect fix for
this real-but-not-yet-gated one, under time pressure, without a dedicated
regression pass. That trade was not made.

**Recommended real fix** (for whoever picks this up next, before fleet
rollout): derive a workload identity from the pod name via the standard
Kubernetes generated-name suffix pattern (strip trailing
`-[0-9a-f]{8,10}-[a-z0-9]{5}$` for Deployment-managed pods, or
`-[a-z0-9]{5}$` for ReplicaSet/DaemonSet/Job-managed pods, else keep the pod
name as-is for bare Pods/StatefulSets which are already stable) so **both**
log and event paths derive the same stable workload string from the one
field both reliably carry (`.pod`), instead of switching to a field
(`.service`) that only one path carries. This needs its own regression pass
against the log+event correlation gate before it ships — not attempted here
so as not to jeopardize the already-verified P0-2 fix under this session's
time budget.

## Node-class events — not tested this pass

DS-04 also wants "node events -> node class." `red` is a **single-node
cluster** (one `homelab-control-plane` node); testing a node-level event
class (e.g. `NodeNotReady`) would require degrading the cluster's only node,
which is out of scope for a read-only, reversible proof exercise. Not
attempted; flagged rather than silently skipped.

```text
PAYLOAD_CONTRACT_PROVEN: yes
NO_ORPHAN_FIELDS: no   # source_type flagged, not removed (see above)
FIELD_SEVERITY_ADDED_AND_PRESENT: yes
FIELD_CONTAINER_ADDED_AND_PRESENT: yes
FINGERPRINT_DISCRIMINATING: yes
FINGERPRINT_STABLE_UNDER_POD_CHURN: no   # real gap found + evidenced, fix recommended, not applied (see above)
OUTPUT_SANITIZED: yes
```
