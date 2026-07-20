# Phase 2 — Vector: applied config, per-control rationale

Live config as applied: `../applied-config/02-vector-with-metrics.yaml`
(`argo-events/vector-telemetry-triage-red-config` ConfigMap +
`vector-telemetry-triage` Deployment/Service). Delta vs
`../reference-config/02-vector.yaml` is exactly one additive control (the
metrics sink below) — see `../applied-config/README.md`.

## Per-control rationale

| Control | Where | What it costs if removed |
|---|---|---|
| **Redaction** (DS-05) | `normalize` transform, `redact()` on raw `message` before anything else touches it | Secret-shaped values (`password=`, `token=`, `Bearer ...`) reach Kafka/agent/GitLab in plaintext — this is the exact P0-1 defect re-proven in `phase0-*`. |
| **Allow-listed envelope** (DS-05) | `. = {...}` at the end of `normalize` | Without it, raw OTLP `message`/`attributes` (unredacted, unbounded) would be forwarded — the original stress-test failure mode. |
| **Per-line cap** (DS-05) | `truncate(safe_message, 4096, suffix: "…")` | An unbounded log line becomes an unbounded Kafka record / ticket body — cost/DoS risk on the whole downstream chain. |
| **Fingerprint** (DS-04) | `.dedupe_key = sha2(cluster:namespace:pod)` | Without a stable workload identity key, pod churn (restarts) would fragment one incident into many, or unrelated pods could collide. |
| **Correlation key** (DS-04, P0-2 fix) | `.delivery_key = sha2(dedupe_key + reason + representative_log_lines)` used only for **Vector's own** immediate-repeat suppression; **not** the ticketing key | Reusing `delivery_key` as the ticket-dedupe key was the original correlation bug — a later, different-content record (e.g. `BackOff` after a log line) must still reach Argo. Argo's `claim-24h-window` keys strictly on `dedupe_key`, so a later different signal is forwarded and correctly appends. |
| **Severity** (payload gap #1, closed) | `.severity` — event: critical/warning by reason class; log: critical/error by text match | Without it the agent/ticket has no priority signal beyond re-parsing raw text every time. |
| **Container** (payload gap #2, closed) | `.container` from Alloy's `pod_container_name` relabel | Without it, a multi-container pod's failing container can't be isolated from the ticket alone. |
| **Immediate-repeat suppression** | `suppress_exact_repeats` dedupe transform, `fields: {match: [delivery_key]}`, `cache: {num_events: 10000}` | Without it, every duplicate emission of the same tail (e.g. repeated identical log lines) would each cost a Kafka produce + Argo workflow + agent call before Argo's own 24h claim even gets a chance to dedupe. This is in-memory, per-process, no TTL by time — see the "tuning note" below, this shaped several test runs in this pass. |
| **Explicit event-reason allow-list** (DS-15, SIGNAL-COVERAGE) | `incident_signals` filter condition | Without it, every Normal lifecycle event (`Pulled`, `Created`, `Started`, ...) would be produced to Kafka — real measured cost below. |
| **Read-only source** | `alloy_otlp` (OTLP receiver only) | N/A — Vector itself never talks to the Kubernetes API; it only receives what Alloy forwards. |

## Additive-only delta: policy-drop metering (new, this pass)

Added `vector_metrics` (`internal_metrics` source) +
`metrics_exporter` (`prometheus_exporter` sink, port 9598) — required to make
`KNOWN-DEFECTS-AND-REPROVE.md` requirement 3 ("a rejected family shows a
visible drop/quarantine metric") checkable at all; there was previously no
way to observe `incident_signals`' discard count. Does not touch the event
data path (separate source→sink pair, `vector_metrics → metrics_exporter`
only).

## Tried and reverted: disk buffer on the Kafka sink

Attempted to add DS-03's "disk buffer" control
(`buffer: {type: disk, max_size: 268435488, when_full: block}` on the `kafka`
sink, backed by an `emptyDir` + `data_dir: /var/lib/vector`) as a genuine
hardening step, not just documentation. **Result: it broke delivery.**

- The buffer accepted writes fine (`vector_buffer_events{component_id="kafka"}
  = 1`, a 776-byte file appeared under `/var/lib/vector/buffer/v2/kafka`).
- But the Kafka sink never drained it:
  `vector_component_received_events_total{component_id="kafka"} = 0` and
  `vector_kafka_produced_messages_total = 0` stayed at zero indefinitely (only
  librdkafka metadata-refresh requests were observed, no actual produce). A
  throwaway fixture pod's ticket was never created while this was live.
- Reverted immediately (removed the `buffer:` block, `data_dir`, the extra
  volume/mount, and the bumped resource limits) and re-verified: a fresh
  fixture (`phase2-sanity-check-v2`) produced a ticket
  ([#479](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/479))
  end to end again within seconds, and `vector_kafka_produced_messages_total`
  incremented normally.

**Conclusion for whoever promotes this to fleet-grade (DS-03,
`VECTOR_FLEET_GRADE`):** on Vector `0.45.0-debian`, a `type: disk` buffer
paired with the `kafka` sink did not drain in this environment — this needs
its own isolated investigation (a minimal repro outside this pipeline, a
Vector version check/upgrade, or an alternate approach such as an explicit
`batch`/`request` tuning) before it is safe to rely on for a real outage.
Documented here rather than silently dropped so the next pass does not
re-discover it the hard way. The applied config today deliberately runs
**without** a disk buffer (default in-memory buffering only) and is
proven working end to end; it has no bounded local durability across a
Confluent outage or a Vector pod restart — an incident's log/event record in
flight at that moment is lost, not queued. HA (multiple replicas + PDB +
topology spread) was not attempted this pass: `red` is a single-node cluster
(`kubectl get nodes` → one `homelab-control-plane` node), so topology-spread
constraints and cross-node replica placement have no real target to prove
against here regardless of what the manifest says — a cluster-shape
limitation of the proof environment, not a decision to skip the control.
Separately, Vector's in-memory `suppress_exact_repeats` dedupe cache is
per-process, so naively scaling replicas on a multi-node office cluster would
still fragment repeat-suppression across instances; a real HA design needs
either sticky partitioning upstream or moving repeat-suppression to a shared
store. Both remain explicit, named gaps for office/fleet promotion, not
silently-claimed-done items.

```text
WORKER_ALLOY_READ_ONLY: yes
WORKER_VECTOR_REDACTION: yes
WORKER_VECTOR_CORRELATION: yes
VECTOR_FLEET_GRADE: no   # disk-buffer attempt failed+reverted (documented above); no HA/PDB/topology-spread attempted; policy-drop metrics ARE live
ENVELOPE_EFFICIENCY_MEASURED: yes   # see phase2-efficiency.md
OUTPUT_SANITIZED: yes
```
