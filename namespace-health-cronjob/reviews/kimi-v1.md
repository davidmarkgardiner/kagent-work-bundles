# Independent review — Namespace health job, Revision 1 (7 Oct 2026)

**Review type:** supplied-material review of the plan text only. No repository, cluster, Kafka, or Argo inspection was performed, and no prior review was consulted. Reviewer: Kimi (this is the Kimi review named in §7 step 1; treat model agreement as no substitute for the live evidence the plan itself demands).

## 1. Verdict

**ACCEPT WITH CONDITIONS.** The plan is unusually honest about its boundaries (statelessness, sampling, first-valid semantics, missing preflight). The conditions below are all narrowable without architecture change; none requires retained state beyond the receipt ConfigMaps already proposed. Two findings (P0-1, P0-2) must be resolved in the frozen plan text before code, because they determine whether the headline rules are implementable as written.

## 2. Is one stateless scheduled job the smallest sufficient design?

Yes, with one trim. The stated contract — state + Events + application-only log-error detection, one bounded summary to Kafka for Argo — genuinely requires all three read paths; dropping logs would silently drop log-only faults, and dropping Events loses corroboration for unschedulable/OOM evidence. What can shrink without harming the contract:

- **Defer the optional retained-store adapter (§3) entirely out of the pilot.** It is already conditional; make it explicitly post-milestone so the pilot has exactly one log path. Nothing in the acceptance matrix needs it.
- The Argo receiver is not optional if "forwards to Kafka for Argo" is the deliverable, but the receipt-only WorkflowTemplate is the minimal form of it. Keep.

Do not go smaller than one job + one receiver: moving dedup into the assessor or adding an outbox would reintroduce the retained state the plan correctly rejects.

## 3. Findings

**P0-1 — Rule durations have no named evidence source (§4 table, rules 100/90/80-unschedulable vs §3 "current state at assessment time").**
Failure scenario: a Deployment's Pods crash-looped for 4 minutes before the run, or became unavailable 30 seconds ago. The job reads state once; "continuous unavailability supported for at least five minutes" cannot be established unless the plan names the exact fields that prove duration (e.g., Deployment `available=False` condition `lastTransitionTime`, pod container `state.waiting`/`lastState` timestamps, Event series first/last observed). As written, implementers will either invent duration (violating §4's own prohibition) or silently weaken the threshold.
Smallest correction: add one column or footnote to the rule table naming the provenance field per duration claim, and state that absence of the field demotes the rule to contextual (score 60) evidence.
Acceptance test: fixture crash-loop aged 2 minutes must not qualify rules 100/90; aged 10 minutes with verifiable `lastTransitionTime` must qualify; fixture with timestamp fields stripped must demote, not qualify.

**P0-2 — Log rule (80) may be unprovable inside its own read budget (§3 logs, §6 budgets).**
Failure scenario: "20 recognized error records spanning five minutes" against a 128 KiB tail with a fixed since-time. A chatty container's 128 KiB tail may cover only the last 90 seconds; the five-minute span can then never be demonstrated, and the rule silently never fires on exactly the noisy workloads it exists for — a sampled-log bias in reverse (under-detection on high-volume loggers, and deterministic slot rotation means a workload whose errors recur only at a fixed hour is *permanently* uninspected at other slots).
Smallest correction: state that the span requirement is evaluated only within inspected content and record `earliest_inspected_timestamp`; if the tail doesn't reach the window start, report the finding as a lower-bound count with a truncated-coverage flag and let the threshold be a calibration decision at step 4, not a frozen constant. Rotate healthy-workload selection across consecutive slots, not by absolute slot number.
Acceptance test: fixture emitting 20 errors/5 min in a high-volume container (tail covers <5 min) yields a flagged lower-bound result, never a silent miss and never a "namespace error rate" claim.

**P1-1 — First-valid-report conflict handling is specified but its consequence is understated (§5).** If the first valid payload was produced from a truncated/budget-exhausted run and the retry carries the real severe finding, first-valid wins and the worse truth is suppressed until the next slot. The correction is not changing semantics (they're right) but making conflicts a first-class receiver alert with its own acceptance row, not a log line. Test: same slot, body A (partial coverage) then body B (severe finding) → one receipt, conflict surfaced as a visible receiver output.

**P1-2 — Argo receiver topology assumed, not verified (§5).** EventSource/Sensor in an "isolated receiver namespace" depends on whether the home-lab Argo Events install is namespaced or cluster-scoped and whether the eventbus is reachable cross-namespace. The exact required receiver change is: one new dedicated EventSource (new trial topic), one new Sensor, one receipt-only WorkflowTemplate, in the isolated namespace, **without touching the legacy `observability.triage.v2` Sensors**, which expect individual incident fields and would either reject or mis-parse the envelope. Move this verification into §7 step 2 preflight as a named item.

**P2-1 — Envelope drop risk (§1, §5).** A fourth qualifying namespace exists only as a total in the envelope; one failed Kafka send loses all three findings. Acceptable for hourly routine signal, but the plan should state explicitly that consumers must never treat the envelope as a complete cluster inventory.

**P2-2 — External freshness monitoring is a hard dependency dressed as reuse (§6).** "Reuse external CronJob freshness monitoring" — if it doesn't exist for this CronJob, silence is indistinguishable from health. Make its existence a preflight gate with a named fallback (§6 already hints this; promote it).

## 4. Removable machinery and dishonest guarantees

Removable: optional Loki/store adapter (defer, above); no PostgreSQL, no Vector, no sidecar, no runtime pip — already correctly excluded. Keep the receipt ConfigMaps; they are the minimum dedup boundary.

Cannot honestly be guaranteed without retained state, and the plan already declines them: recovery events, two-observation temporal confirmation, sub-hour incident capture, duplicate-free *effects* beyond the receipt (lightweight replay workflows will still run), and any daily volume quota. I would not add any of these; the stated contract doesn't need them. What must *not* happen is quietly upgrading claims later — e.g., calling sampled matched counts namespace rates, assuming a Loki exists from Alloy config, or claiming duplicate-free downstream effects from receipt dedup alone.

## 5. Envelope vs. legacy v2 path

One cluster envelope with up to three namespace findings fits the need: the question is "which namespaces, why," not "which pods." Required receiver change, exactly: new schema `namespace-health.report.v1` on a dedicated trial topic; new EventSource + Sensor + receipt-only WorkflowTemplate; payload passed as data, never interpolated into executable source; validation of schema, trusted source, slot age ≤2h, skew ≤5min before any receipt. The legacy v2 path must remain byte-identical and unmodified — the plan's "do not fabricate legacy pod fields" is the correct hard line.

## 6. Five strongest home-lab falsification tests

1. **Log-only fault, ready Pods:** fixture with all Pods Ready emitting ≥20 structured errors/5 min; assert the log rule qualifies with declared coverage — proves it isn't a readiness checker. Pair with an info-flood fixture asserting no publication (guards the inherited Alloy `info`-drop regression).
2. **Duration honesty:** crash-loop aged <5 min and a yesterday-terminated container; assert neither qualifies availability rules (P0-1).
3. **Slot conflict:** publish slot X with body A, kill/restart the Job, republish with changed body B; assert exactly one receipt, duplicate vs. conflict correctly distinguished, conflict visible.
4. **Budget exhaustion:** >24 eligible containers and oversized logs; assert partial/unknown coverage flags, runtime under ceiling, no all-healthy claim, no silent omission.
5. **Broker outage + recovery:** publish during Kafka downtime; assert visible failure, bounded retries, no success claim, and no old-window catch-up storm after recovery. Companion: suspend the CronJob and confirm the *external* freshness check fires.

Workplace prerequisites: verified cluster identity source, reachable Kafka with TLS/SASL details, Argo Events install mode (namespaced vs cluster), existing external freshness monitor, offline build host and digest-locked base image on linux/amd64, and workplace consumer/schema compatibility plus its own canary.

## 7. Recommended build order

Decide **before code**: (a) named duration-provenance fields per rule (P0-1); (b) log span/truncation semantics and rotation scheme (P0-2); (c) trusted cluster identity and `slot_id` inputs; (d) slot resolver for the installed K8s version; (e) receiver namespace/eventbus topology; (f) existence of the external freshness monitor. Then: schema + rules offline with fixture tests → report-only cluster run with measured costs → Kafka↔Argo transport proof including conflicts and outages → real three-hour soak → workplace bundle. Freeze the revised plan text, including the P0 dispositions, at step 1 as proposed.
