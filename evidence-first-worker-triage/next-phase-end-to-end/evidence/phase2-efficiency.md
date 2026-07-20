# Phase 2 — Efficiency: numbers, not adjectives

All numbers scraped from Vector's own `prometheus_exporter` sink (port 9598,
added this pass — see `phase2-vector-config.md`), `red`, 2026-07-20.

## Snapshot A — Gate-0 window (clean Vector process, after restart)

```text
alloy_otlp        (received)                121
normalize         (received)                121
incident_signals  (received)                121
incident_signals  (discarded, intentional)   14   # 11.6% policy-filtered
suppress_exact_repeats (received)           107
kafka             (received / produced)       6   # 5.6% of raw input reaches Kafka
```

## Snapshot B — Phase-1 window (cumulative, same process, heavier Unhealthy/BackOff bursts)

```text
alloy_otlp        (received)                260
incident_signals  (discarded, intentional)   67   # 25.8% -- higher because repeated
                                                    Unhealthy probe failures and repeated
                                                    BackOff/Normal noise from the same
                                                    fixtures pushed more Normal-adjacent
                                                    records through normalize
suppress_exact_repeats (received)           193
kafka             (received / produced)      78   # 30% of raw input -- most of what
                                                    passed policy was NOT an exact repeat
                                                    in this window (distinct probe-failure
                                                    timestamps => distinct delivery_key)
```

## Snapshot C — bytes/envelope (post-revert clean process)

```text
alloy_otlp / normalize (received bytes / events)   7564 / 9   = 840 bytes/record average (raw OTLP in)
kafka (received bytes / events)                    1680 / 2  = 840 bytes/record average (after redact+allow-list, to Kafka)
```

Note the raw-in and to-Kafka average happen to match closely in this small
sample (both ~840B) — the allow-listed envelope removes OTLP wrapper
overhead (resource/scope attributes, protobuf framing) roughly in proportion
to what redaction adds back via placeholder text, at this sample size. This
is not a claim that redaction is free — `PAYLOAD-FIELD-PROOF.md`/Phase 4 is
where per-field byte accounting belongs; this snapshot is Phase 2's
"efficiency is measured, not asserted" bar.

## What each stage removes and why (no silent drops — SIGNAL-COVERAGE rule)

| Stage | Removes | Because |
|---|---|---|
| `incident_signals` (policy filter) | Normal lifecycle events (`Pulled`, `Created`, `Started`, `Scheduled`), non-matching Warning noise (e.g. Kyverno `PolicyViolation` text that doesn't match the incident regex) | Explicit, versioned allow-list (`SIGNAL-COVERAGE.md`) — metered via `component_discarded_events_total{intentional="true"}`, not silently absent. |
| `suppress_exact_repeats` (in-process dedupe) | Byte-identical repeats of the same `delivery_key` within the process's cache window (10,000-event LRU, no time TTL) | Documented, intentional (`RED-PROOF-README.md`: "Vector removes immediate duplicate records in memory"). **Practical effect observed this session:** re-firing an identical synthetic fixture against a long-lived Vector process produces zero new Kafka records — this is why several test iterations in `phase0`/`phase1` required a Vector restart to get a fresh `delivery_key` cache for repeat-content fixtures. Real incidents naturally vary in timestamp/content per occurrence, so this shapes fixture-writing more than production behaviour. |
| Argo `claim-24h-window` (downstream, not Vector) | Everything past the first claim for a given `dedupe_key` within 24h | The authoritative dedupe boundary (see `phase0`); Vector's in-process suppression is a pre-filter, not the guarantee. |

## Efficiency conclusion

The pipeline visibly does the cheap filtering (policy match, exact-repeat
suppress) before anything touches Kafka, the agent, or GitLab — the expensive
steps (Kafka produce, Argo workflow, agent A2A call, GitLab API call) only run
for the 6-30% of raw records that survive both filters in these samples, and
zero for records already ticketed within the 24h window.

```text
ENVELOPE_EFFICIENCY_MEASURED: yes
```
