# Evidence specification and execution record

Revision 6. Test requirements changed after [review](REVIEW-FEEDBACK.md). B1 execution and the accelerated B2–B4 lab build ran on 2026-09-15; the daily workplace source bundle passed offline gates on 2026-09-16. This file distinguishes working implementation from unearned promotion claims.

## Current evidence

| Claim | Status | Basis |
|---|---|---|
| Initial plan independently reviewed | REVIEWED: REVISE BEFORE BUILD | Original feedback preserved in this directory |
| Revision 2 answers the findings | AUTHOR RESPONSE RECORDED | [Review register](REVIEW.md); follow-up verdict pending |
| Candidate sources inspected | SOURCE REVIEWED | Pinned monitor and existing sentinel/certification source |
| B1 local report and monitor corrections | LAB IMPLEMENTATION PASS / LIVE | [B1 implementation](b1/README.md), [initial receipt](b1/evidence/2026-09-15-live-smoke.md), and [accelerated receipt](evidence/2026-09-15-accelerated-lab.md); elapsed calibration and acceptance incomplete |
| B2 current-state transfer | SINGLE-CLUSTER LIVE; EARLIER TWO-API-SERVER PASS | [Single-cluster receipt](evidence/2026-09-15-single-cluster.md): compiled amd64 intake accepted new sequence 41 after a clean restart; prior bounded authenticated intake, partial/outage/restore drills also pass; Kafka and independent-host proof not run |
| B3 evidence-only agent value | MODEL HARNESS PASS / KAGENT VALUE NOT RUN | [Model receipt](evidence/2026-09-15-model-proof.md): real model call, deterministic severity, exact supplied claim IDs, zero tools; no deployed kagent Agent or SRE value comparison |
| B4 real GitLab summary reuse | LOCAL LEDGER PASS / GITLAB NOT RUN | One stable summary create/update/replay/closed behavior; external writes zero |
| Workplace readiness | OFFLINE BUNDLE PASS / WORKPLACE NOT RUN | [Daily/GitLab offline receipt](evidence/2026-09-16-daily-gitlab-bundle-offline.md); internal Fox adaptation, images, scans, Kafka, AKS-MCP authorization, GitLab, deployment, fault drill and soak still require real workplace evidence |

## Plan-package checks

Revision 2 validation on 2026-09-15 passed all 24 relative-link checks across seven Markdown documents, whitespace checks, and the strict public-safety scan. The response register contains all 19 review findings; the evidence matrix contains E01–E30. The original feedback's SHA-256 remained `5776dcb940f059e65b4832e10bdcc20ce58d15f33c63c33ea8b64f82ba987033`. Planning checks are not runtime proof.

## B1 execution ledger

Run `B1-20260915-live` is documented in [the dated receipt](b1/evidence/2026-09-15-live-smoke.md).

| Evidence | Disposition | Current basis and limit |
|---|---|---|
| E01 | PARTIAL PASS | Live immutable report with no downstream dependency; successful Job exclusion proven by sanitised fixture, not a live completed Job in pilot scope |
| E02 | PARTIAL PASS | Real timestamp shapes plus old/new OOM fixture pass; startup/readiness transition drill remains |
| E03 | PARTIAL PASS | Rolling restart delta/reset unit proof and stable live observations; live reset/pruning fault remains |
| E04 | PARTIAL PASS | Live RBAC denial and fail-closed section design; dedicated 403/log-failure drill remains |
| E05 | PARTIAL PASS | 50 replacement pods collapse to one stable group; hour-long churn replay remains |
| E07 | PARTIAL PASS | Stable owner/symptom grouping passes; related/unrelated node-association fixture remains |
| E08 | PASS | All 1,024 domain combinations, unknown coverage, and 1 versus 200 of 1,000 pass |
| E09 | PARTIAL PASS | Original snapshot age is exported; three-interval stale and republished-old-data drill remains |
| E10 | PARTIAL PASS | Raw log lines are not retained and snapshots are capped; sensitive/oversize adversarial fixtures remain |
| E11 | PARTIAL PASS | Secrets/workload writes/non-allowlisted reads denied live; tenant-admin mutation drill remains |
| E13 | PARTIAL PASS | 1,000 missing-limit containers produce one advisory aggregate; active-identity pressure drill remains |
| E23 | PARTIAL PASS | Schedules, 30-minute deadline, missed-slot auditor, and DST uniqueness pass; controller outage is not live-drilled |
| E24 | STARTED | Collector is running; 10 working days, real weekend, 20 labelled slots, and SRE acceptance remain |
| E27 | PASS | Missing/invalid downstream flags and unsafe bounds fail before collection; no downstream fields or client exist |
| E28 | PARTIAL PASS | 93.6% CPU fixture and PolicyViolation allowlist behavior pass; live full-placement/CNI headroom remains unavailable |

B2–B4 accelerated evidence is recorded in [the dated lab receipt](evidence/2026-09-15-accelerated-lab.md), with the bounded model run in [the model receipt](evidence/2026-09-15-model-proof.md) and current placement in [the single-cluster receipt](evidence/2026-09-15-single-cluster.md). It does not convert real-time, deployed-kagent, GitLab, reviewer, SRE-value, or workplace gates into passes.

## Build-specific acceptance matrix

The matrix defines the complete target. Current B1 dispositions and limitations are in the dated run receipt; tests without a dated receipt remain NOT RUN. IDs are retained where useful, but requirements below supersede the original E01–E26 matrix. In particular E12/E13 test aggregation and snapshots, not a new delta-stream implementation.

| ID | Build | Scenario and required result |
|---|---|---|
| E01 | B1 | Real healthy resources and completed Job pods: useful local report, no false not-ready outcome, no broker/model/ticket dependency |
| E02 | B1 | Real timestamp formats, old/new OOM/logs, startup and readiness changes: recency and duration correct; unknown history explicit |
| E03 | B1 | Restarts across a rolling window, reset, and observation pruning: correct deltas or partial coverage, never silent healthy |
| E04 | B1 | Missing permissions, log/scanner failure, absent metrics, suppression read 403: affected coverage partial, error visible, no false resolution |
| E05 | B1 | 50 replicas churn for an hour with pod/event/log overlap: at most one group per workload/symptom, fewer than 10 group-state entries for the single-workload fixture |
| E06 | B2 | Same names in two worker identities, wrong cluster or namespace: separate state, spoof rejected; label simulated and real topologies distinctly |
| E07 | B1 | Related/unrelated failures and unscheduled pods: grouped only with supporting evidence; no invented node association |
| E08 | B1 | Enumerate all 1,024 domain outcomes plus unknown cases: shared-services degraded breaches, delivery critical breaches, incomplete coverage never recovers; 1 versus 200 of 1,000 unavailable workloads differs |
| E09 | B1/B2 | Quiet healthy scan versus missing heartbeat; old data wrapped in a new snapshot: original observation age retained; stale within configured intervals |
| E10 | B1/B2/B3 | Sensitive-value and instruction fixtures, oversized input: redaction and truncation explicit; no unsafe data in reports/agent/tickets; source text is never executable |
| E11 | B1/B2 | Tenant admin and collector denials: tenant cannot obtain producer credential or mutate aggregate source; collector cannot read secrets/exec/write workloads; non-allowlisted namespace quarantined |
| E12 | B4 | 20,000 raw observations for one scheduling cause fed locally: bounded group state and snapshot bytes; snapshot publication bounded by schedule, not raw count; one summary and one admitted analysis for an unchanged assessment |
| E13 | B1/B4 | 1,000 containers without limits: zero per-container hygiene findings and one namespace aggregate. High-cardinality group/state pressure: no active-identity eviction loop, partial trend coverage and limits visible |
| E14 | B3/B4 | Concurrency and hourly/create budgets hold across restarts; four changes before noon cannot consume reserved 16:30 update; blocked changes displayed |
| E15 | B2 | Broker unavailable 30 minutes with 100 active findings: zero publisher-induced monitor restarts, poll p95 within declared tolerance, one pending snapshot plus bounded in-flight record, fresh-state convergence after reconnect |
| E16 | B2 | Duplicate snapshot, worsening state, recovery, then old replay: each newer sequence applied correctly; checksum conflict quarantined; same-state timestamps do not dispatch analysis |
| E17 | B3 | Crash after request reservation/submission, workflow retry: deterministic request/workflow identity, no extra budget or blind model re-execution |
| E18 | B4 | GitLab accepts write before connection/process failure; missing mapping or label: exact label reconciliation or explicit blocked state, never blind duplicate create |
| E19 | B4 | API outage/rate limit, closed/deleted issue, exhausted budget: bounded retry, visible pending/conflict state, deterministic report remains available |
| E20 | B2/B4 | Old database restore: next complete snapshot restores current health. Side effects stay paused until labels/operations/budgets reconcile; unknown spend is conservatively reserved |
| E21 | B2/B4 | Historical catch-up, compaction lag, stale generation/sequence, tombstone: coalesce with side effects off; no per-record dispatch, no old resolution or snapshot regression |
| E22 | B3 | Tool-free agent with worker-only namespace: zero tool/delegation calls; absent detail marked unknown; invalid/unsupported citations fail evaluation; timeout preserves deterministic report |
| E23 | B1/B2/B4 | Controller down 07:00–08:30: 07:30 slot recorded missed with 30-minute grace. Shorter outage produces one labelled late slot. DST does not duplicate a slot or consume reserved updates twice |
| E24 | B1/B4 | At least 10 working days spanning a real weekend and 20 labelled weekday slots: per-rule false-positive rate, operator acceptance, measured cost; separate authorised ticket trial |
| E25 | B4 | Stop-write and rollback: mappings/offsets/evidence retained, only scoped fixtures removed, urgent alerting remains functional |
| E26 | Handoff | Same images/schemas/rules render with workplace placeholders; migrations, restore, permission/consumer inventory, and rollback gaps explicit |
| E27 | B1 | `flase`, missing downstream flag, invalid bounds: collection/readiness fails closed, no publisher created; triage flags absent from adapter output |
| E28 | B1 | Recorded 93.6% CPU-commit fixture is watch/degraded; 1,000 audit-only PolicyViolation events create zero findings and visible excluded count; CNI-inapplicable headroom is unavailable |
| E29 | B2 | An ongoing group falls out of top-N, and a newer snapshot is partial: neither resolves the group or cluster; explicit complete zero/exhaustive membership required |
| E30 | B4 | Both incident and state lanes enabled for one crash loop: at most one incident issue plus one health summary linking it; summary writer never creates a workload ticket |

## Data fidelity and limits

Capture sanitised Kubernetes API responses from a real lab cluster before synthetic scaling. Retain event timestamps, ownership, Job completion, missing fields, and container-state shapes. Use a small live-fault smoke separately from replay and record which path each test proves. The recorded old sentinel snapshot is a regression fixture, not a current lab measurement.

B1 needs no 20,000-record transport test. Its hygiene and 50-replica fixtures establish relevant cardinality behaviour. B4 can stress a local aggregation function with 20,000 observations and separately stress central snapshot catch-up. Do not create 20,000 pods, model calls, or real issues.

Bounded top-N detail cannot prove per-group absence. E29 is mandatory before any recovery/ticket behaviour. Losing intermediate snapshots is an accepted limitation, not a PASS for historical lossless delivery.

## Performance and calibration acceptance

Declare host capacity, namespace/pod counts, rule set, input bytes, and resource limits before measuring. Initial polling target is p95 below the configured poll interval. For E15, define a tolerance before the run, initially no more than 10% p95 increase over the same 100-finding fixture with a healthy broker. Re-estimate if the lab cannot meet it; report measurements rather than silently relaxing the target.

Record list calls, API response/log bytes, memory, throttling, and state growth per namespace. Use them in the pre-B2 process/shard decision. Snapshot publication stays at one per configured interval per worker, with bounded retry/in-flight behaviour. After restore, current state converges on the next healthy complete interval; history and external side-effect state have separate recovery gates.

For E24, retain at least 20 labelled weekday slots plus the weekend observations. Record per-rule true/false positives, missing evidence, and important incidents that were missed. SRE accepts rule scope and thresholds explicitly; twenty samples alone do not establish a statistically general error rate. Measure report-only resources/operator time and B3 tokens only if B3 runs.

## Per-run receipt template

```text
Run ID and test IDs: {{RUN_AND_TEST_IDS}}
Build and plan revision: {{BUILD_AND_PLAN_REVISION}}
Started / ended UTC: {{START_AND_END}}
Operator / reviewer: {{ROLES}}
Source commits / image digests / component versions: {{VERSIONS}}
Topology and real API-server count: {{TOPOLOGY}}
Private environment record: {{PRIVATE_REFERENCE}}
Rules / baseline / schema versions: {{POLICY_VERSIONS}}
Expected namespaces/checks and exclusions: {{COVERAGE}}
Mode and budgets: {{MODE_AND_BUDGETS}}
Fixture hashes and expected counts: {{FIXTURE_REFERENCE}}
Commands, exit codes, observed counts and resources: {{MEASUREMENTS}}
Snapshot generation / sequence / checksum: {{SNAPSHOT_REFERENCE}}
Assessment / request / workflow / A2A / issue IDs where applicable: {{CORRELATION}}
Result: NOT RUN
Limitations and missing evidence: {{GAPS}}
Cleanup and recovery receipt: {{CLEANUP_REFERENCE}}
```

Keep private endpoints and credentials outside public receipts. Include machine-readable counts, bounded input/output examples, fixture hashes, and cleanup results. Screenshots supplement those artifacts. Use `scripts/public-safe-scan.sh` before sharing and document sanitisation changes. The evidence reviewer records achieved scope and exclusions; waivers never convert failed tests to PASS.
