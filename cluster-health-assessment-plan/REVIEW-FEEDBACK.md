# Plan review feedback

Status: plan review only. No runtime evidence was produced. Nothing was built, deployed, published, or ticketed.

| Field | Value |
|---|---|
| Reviewed | README, ARCHITECTURE, PLAN, EVIDENCE, REVIEW, WORK-HANDOFF in this directory (uncommitted working copy, 2026-09-15) |
| Source inspected | `autonomous-monitor` at `7c785b574c36f7100ae321ec0f880782dfead311` (cloned read-only); local sentinel README and orchestrator Agent; baseline-sentinel bundle README; dual-source Kafka routing doc |
| Reviewer | Claude (Opus 5), acting as the plan critic. Not the plan author. |
| Verdict | **REVISE BEFORE BUILD** |

Line references to upstream use the pinned commit, for example `monitor.go:258` means
`https://github.com/foxj77/autonomous-monitor/blob/7c785b574c36f7100ae321ec0f880782dfead311/monitor.go#L258`.

## Summary

The plan handles risk well. It separates health score, coverage, and triage mode. It sets budgets centrally, does not claim exactly-once GitLab writes, treats missing data as unknown rather than healthy, and never counts a positive review as permission to build. Those parts should stay.

Three problems block a build decision:

1. **The design streams per-finding changes when it could send whole snapshots.** Most of the hard work comes from that choice: the spool, resolution ordering, record deduplication, inventory reconciliation, and replay handling. A complete, bounded snapshot per cluster, sent on an interval, avoids nearly all of it. The existing sentinel already works this way.
2. **The first useful output arrives too late.** The README says the deterministic report comes first. In the plan it comes in Phase 4, after cross-cluster Kafka transport has been proven. The 10–15 day estimate does not fit eight phases, 26 mandatory tests, a new Go service, PostgreSQL with an outbox, a spool, a writer ledger, and three API servers.
3. **The upstream monitor has storm-shaped defects the plan does not list.** These are pod-name finding IDs, resource-spec findings that are on by default and fill the state cap, a poll loop that stalls when the broker is down, and configuration parsing that fails open. Any one of them can cause the kind of flood this plan exists to prevent.

The agent placement also needs one explicit rule (F01). Otherwise the agent on the agentic cluster will silently investigate the wrong cluster.

## Smallest viable first build

Build the report before any transport, agent, or ticket work.

| Build | Scope | Explicitly excluded |
|---|---|---|
| **B1: report on one worker** | Reuse sentinel certification checks and `check-baseline` drift rules (node CPU commit, pod-CIDR/max-pods headroom). Add the corrected monitor as a source of per-namespace aggregate counts only. Produce a morning/evening report as an immutable ConfigMap or artifact, plus a Grafana view. Report-only. | Kafka, PostgreSQL, agent, GitLab, second cluster |
| **B2: snapshot transport** | Each worker publishes one bounded, sequence-numbered cluster snapshot per interval to a per-cluster topic (compacted, keyed by cluster). A central service stores the latest complete snapshot and computes assessments. Staleness comes from missing intervals. | Per-finding deltas, local spool, outbox |
| **B3: bounded agent** | Evidence-only agent with no Kubernetes tools (F01), one request per changed assessment, budgets in PostgreSQL | GitLab |
| **B4: sandbox ticket** | Writer ledger, label-keyed reconciliation (F14), one issue per cluster | Workplace project |

Re-estimate after each build. Components to remove from the first build: local publication spool, per-finding Kafka contract, outbox, writer, second and third API servers, and 20,000-record replay. Keep them in the backlog until B2 shows they are needed.

## Findings

Severity: **Critical** can cause a ticket storm, silent evidence loss, or a false healthy report with no signal to the operator. **High** blocks the build decision. **Medium** must be fixed or explicitly deferred before the affected phase starts. **Low** is advisory.

Type: `impl` = upstream or implementation defect, `design` = design gap, `policy` = tunable choice, `work` = workplace prerequisite.

### F01 — Agent on the agentic cluster will query the wrong cluster · Critical · design

- **Reference:** ARCHITECTURE §Agent handoff and security; PLAN Phase 5 step 3; baseline-sentinel README "The one architectural constraint"; `agents/cluster-health-sentinel/05-orchestrator-agent.yaml` lines 92–146.
- **Scenario:** `kagent-tools` uses its in-cluster ServiceAccount. The existing orchestrator has eight `k8s_*` tools and a `k8s-readonly-agent` sub-agent. If Phase 5 reuses that agent or copies its tool list (the plan encourages reuse), every tool call on the agentic cluster returns facts about the agentic cluster. No call errors, so the ticket confidently describes the wrong machine. The plan says "fixed tool allowlists" and "no worker API access" but never says the agent must have **no** Kubernetes tools.
- **Correction:** Create a new Agent CR with zero `k8s_*` tools and no sub-agents that hold them. Add a `validate-agent-cr.py` rule that rejects Kubernetes tools on agents labelled for evidence-only analysis. State what the evidence-only agent adds beyond the deterministic report. The sentinel's best results came from tool use (checking restart age, finding 699% overcommit), so if the answer is "little", move B3 after B4 or drop it.
- **Acceptance:** Send an assessment that names a namespace existing only on the worker. The agent records it as missing evidence, makes zero tool calls, and the result validator rejects any claim not backed by an evidence reference.

### F02 — Per-finding delta streaming creates avoidable failure modes · Critical · design

- **Reference:** ARCHITECTURE §Data contracts (chronology, partial scans, complete inventory), §Delivery and storage (steps 1–5, spool sizing); EVIDENCE E03, E09, E15, E16, E21.
- **Scenario:** Deltas have to be ordered, deduplicated, replayed, and reconciled. The plan accepts that and then adds a spool, sequence validation, stale-resolution auditing, inventory reconciliation, and a 30-minute outage sizing exercise. Every added mechanism is another place to lose or duplicate state. After a database restore, central state cannot be rebuilt from the monitor, because the monitor republishes a finding only when it is new, changed, or failed (`monitor.go:221-226`).
- **Correction:** Make a complete, bounded cluster snapshot the primary contract. Each snapshot carries `cluster_id`, `snapshot_seq`, coverage per check family, grouped counts, the top-N findings, and a checksum. The next snapshot replaces the last one, so a lost snapshot only causes staleness, never wrong state. Resolution becomes "absent from a complete snapshot". The plan already requires "periodic complete inventory summaries"; promote that from reconciliation aid to the contract itself, and defer deltas.
- **Acceptance:** Stop the broker for 30 minutes. Coverage goes stale after three intervals. The first snapshot after reconnect restores the correct assessment with no replay, no spool, and no duplicate side effects. Restore the database from an old backup, and state is correct after one interval.

### F03 — First useful output comes too late; estimate does not fit scope · High · design

- **Reference:** README §Intended outcome; PLAN §Scope and owners (10–15 days), Phases 1–4.
- **Scenario:** The morning/evening report is the stated first outcome, but it depends on Phase 3 transport across separate API servers ("a successful local broker test does not pass this gate"). A lab infrastructure problem in Phase 3 blocks the only output SRE can use. The 10–15 day figure does not cover a new service, migrations, outbox, writer ledger, spool, 26 tests, and a 72-hour soak.
- **Correction:** Reorder as B1–B4 above. Put the estimate at the top of each build, and re-estimate at every gate.
- **Acceptance:** SRE reviews a B1 report on one worker before any Kafka topic exists.

### F04 — Pod-name finding IDs turn pod churn into new findings · Critical · impl

- **Reference:** `finding.go:54-57` (ID = hash of namespace, kind, name, check, reason); `checks.go:68-76, 91, 96` (pod name used as the name); PLAN Phase 2 step 2 ("owner-reference enrichment").
- **Scenario:** A crash-looping Deployment that replaces pods gets a new finding ID for every replacement. Each one publishes as new and resolves the old one. A single scheduling problem also yields up to three findings per pod (`pending-too-long`, `not-ready`, and a `FailedScheduling` event finding). Owner *enrichment* adds fields but leaves the key alone, so churn continues to drive Kafka volume and the 2,000-finding state cap. The plan's defect list does not include this.
- **Correction:** Rekey findings at workload level (`cluster | namespace | ownerKind | ownerName | symptom-family`). Report pod instances as counts and bounded examples. Collapse pending, not-ready, and `FailedScheduling` for the same pod into one symptom family. Do this in the monitor patch, not the central service, so the state cap sees workload keys.
- **Acceptance:** A 50-replica Deployment crash-loops for one hour with pod replacement. Result: at most one finding per (workload, symptom family), published records bounded by state transitions rather than pod count, and state entries under 10.

### F05 — Resource-spec findings are on by default and fill the state cap · Critical · impl

- **Reference:** `checks.go:135-155`; `config.go:107` (`CHECK_RESOURCE_SPECS_ENABLED` defaults on); `monitor.go:381-394` (evicts oldest ongoing findings once over `MAX_FINDINGS`); ARCHITECTURE §Health ("resource-limit hygiene remains advisory").
- **Scenario:** Each container without requests or limits produces up to three findings. At 700 such containers (common in real namespaces) the monitor exceeds 2,000 findings. `pruneFindingCap` then evicts ongoing findings, the next poll rediscovers them as new, and they republish. That publish loop comes from hygiene data the scoring model already ignores.
- **Correction:** Set `CHECK_RESOURCE_SPECS_ENABLED=false` for the pilot. If hygiene is wanted, emit one namespace-level aggregate count. Add a realistic hygiene count to E13.
- **Acceptance:** A namespace with 1,000 containers and no limits produces no per-container findings, no `statePrunes{reason="cap"}` increments, and one aggregate value in the report.

### F06 — Broker outage stalls the poll loop and the liveness probe restarts the monitor · High · impl

- **Reference:** `monitor.go:258-264` (synchronous publish inside `collectFindings`); `main.go:69` with `config.go:75` (10s publish timeout); `health.go:40-49` (default max gap `max(3×poll, poll+checkTimeout)` = 180s); chart `deployment.yaml:151` (liveness probe on `/healthz`); `monitor.go:142` (state saved only at end of poll).
- **Scenario:** With the broker unreachable, each finding that needs publishing blocks for about 10s. With roughly 18 or more pending findings, a poll takes longer than 180s, `/healthz` returns 503, and the kubelet restarts the pod before `maybeSave` runs. The monitor crash-loops, its own namespace grows a CrashLoopBackOff, and when the broker recovers every pending finding flushes at once. The plan's spool design says "remove only after ack" but never says publishing must be decoupled from polling.
- **Correction:** The poll writes to a bounded queue without blocking. A separate publisher drains it, and liveness tracks the poll, not publishing. With F02, keep only the latest snapshot per cluster in the queue.
- **Acceptance:** E15 with at least 100 active findings: monitor restart count stays at 0 during a 30-minute outage, the poll p95 is unchanged, and the post-recovery burst is bounded by queue size.

### F07 — Monitor configuration fails open · High · impl

- **Reference:** `config.go:121-130` (`DOWNSTREAM_TRIAGE_ENABLED` defaults to true when unset); `config.go:177-186` (`boolEnvDefaultOn` returns true for any unrecognised value); `monitor.go:552-556` (errors reading the suppression ConfigMap, including 403, are ignored); PLAN Phase 2 step 1.
- **Scenario:** A typo such as `flase`, a missing value in one overlay, or a Helm values merge that drops the key sets `ai_triage_required=true` on findings published to the default topic `k8s.namespace.findings`. The workplace flood's cause is unverified, and any existing consumer that trusts that flag will fan out. Separately, a suppression RBAC error publishes every suppressed finding without any warning.
- **Correction:** (a) The adapter strips `ai_triage_required` and `cooldown_until`, and the central service never reads them. (b) Add a startup check that fails readiness unless the value is exactly `false`. (c) Patch bool parsing to reject unknown values. (d) Expose suppression-load failure as a metric and in scan status. (e) Add a WORK-HANDOFF step to list every consumer of the monitor's topic before rollout.
- **Acceptance:** Deploying with `DOWNSTREAM_TRIAGE_ENABLED=flase` leaves the pod not ready. Removing the suppression Role shows `suppression_load=error` in the next report.

### F08 — Upstream `id` is a finding identity, not a record ID · High · design

- **Reference:** `finding.go:55` (ID excludes status and score); `monitor.go:286-301` (resolution reuses the same ID); `publisher.go:93` (Kafka key = finding ID); ARCHITECTURE §Delivery step 4 ("redelivery encounters the stored record ID").
- **Scenario:** If the adapter maps `id` to `record_id`, central deduplication drops real changes, such as a score escalating from 60 to 85 or the resolution, because they look like duplicates. The finding stays ongoing and critical escalation is lost. If the adapter uses a random UUID, retries are never deduplicated. The Kafka key also partitions by finding, not by the cluster and workload the plan specifies.
- **Correction:** Define `record_id = hash(finding_key, status, classification, source_seq)` in the Phase 1 contract, and set the partition key per ARCHITECTURE line 75. With F02 this reduces to `(cluster_id, snapshot_seq)`.
- **Acceptance:** Add to E16: redeliver ongoing(60), ongoing(85), and resolved in order. Central state ends resolved, with the escalation recorded once.

### F09 — Health score gating hides whole domains · High · policy

- **Reference:** ARCHITECTURE §Health and automation readiness (weights, breach ≤85, recovery ≥90, overrides only for node, shared-service, or availability rules).
- **Scenario:** Single-domain scores from the proposed weights:

  | Domain (weight) | Watch 80 | Degraded 50 | Critical 0 |
  |---|---|---|---|
  | Nodes (30%) | 94 | **85 → breach, on the boundary** | 70 (override) |
  | Workload (25%) | 95 | **87.5 → neither breach nor recovery** | 75 (override) |
  | Shared services (20%) | 96 | **90 → counts as recovered** | 80 (override) |
  | Resource pressure (15%) | 97 | 92.5 → healthy | **85 → breach only at equality** |
  | Delivery (10%) | 98 | 95 → healthy | **90 → recovered while Flux is fully broken** |

  Degraded DNS alone never breaches. Complete Flux failure reports as recovered. Workload domain degraded sits between the thresholds and never changes state. Because a domain uses its single worst outcome and there are no per-replica deductions, one failing workload and 200 failing workloads score the same unless a critical rule fires.
- **Correction:** Gate on domain status, not the weighted mean: any required domain degraded for two complete assessments is a breach, and any domain critical is an override. Keep the numeric score for trend display only. Set rule outcomes from impact share (for example, over 10% of workloads unavailable is critical) so scale is visible.
- **Acceptance:** A table-driven test enumerates all 1,024 domain-outcome combinations against an SRE-approved truth table. Named cases: shared degraded breaches; delivery critical breaches; 1 vs 200 unavailable workloads give different outcomes.

### F10 — Log and state defects missing from the Phase 2 list · Medium · impl

- **Reference:** `monitor.go:436-441` (under the 900 KiB limit, observations are pruned before findings); `monitor.go:528-532` (state that is still too large is never saved); `checks.go:486-490` (log stream error skipped while the check reports `complete: true`; already in the plan's list, confirmed).
- **Scenario:** Size pressure deletes restart-count and memory-sample observations first, so restart-rate and memory-trend checks silently reset and produce false negatives. If state is still too large after pruning, every write is refused. Each restart then rediscovers every finding as new, and the only signal is `stateWrites{result="too-large"}`.
- **Correction:** Add both to the Phase 2 defect list. Put `state_write_result` and `observations_pruned` into scan status, and mark restart and memory coverage as partial when observations were pruned.
- **Acceptance:** Fill state to the limit. The report shows partial restart coverage, and a monitor restart publishes no rediscovered findings.

### F11 — Tenant namespaces can reach the Kafka credential · High · design

- **Reference:** chart `values.yaml:23-29` and `rbac.yaml` (by default, one monitor per namespace installed into that namespace); ARCHITECTURE §Data contracts (per-cluster topic ACLs); EVIDENCE E06, E11.
- **Scenario:** Under the default chart layout the monitor and its Kafka credential Secret sit in the tenant namespace. Anyone who can read Secrets or exec into pods there holds a producer identity valid for the whole cluster's topic. Topic ACLs bind the identity to the cluster, not to the namespace, so a tenant can publish fake resolutions for other namespaces or inject 20,000 findings. E06 and E11 test cross-cluster spoofing but not cross-namespace spoofing within a cluster.
- **Correction:** Run monitors or a multi-namespace collector in a platform-owned namespace, using `watch.namespace` and RoleBindings into tenant namespaces. Keep the producer credential only there. Centrally, reject records whose namespace is outside that producer's allowlist.
- **Acceptance:** A new E11 case: a tenant namespace admin cannot read the producer credential, and a record claiming a non-allowlisted namespace is quarantined.

### F12 — Sentinel lessons not carried forward · Medium · design

- **Reference:** baseline-sentinel README (858 of 859 warning events were Kyverno `PolicyViolation`; 44 passing unit tests missed a real timestamp-format bug; `node_cpu_commit` was the only check that caught a real problem); `checks.go:431-441` (every warning reason scores at least 50 and becomes a finding); EVIDENCE E12/E13 (synthetic records).
- **Scenario:** Unchanged, the monitor publishes every audit-only policy violation as a finding, repeating the RED noise problem. The test matrix relies on synthetic records, which is exactly how the sentinel's timestamp bug got through. The drift rule that caught the real RED problem does not appear as a named rule in the scoring domains. "Versioned baseline" in the plan means an accepted healthy period, which is a different idea.
- **Correction:** Use an event-reason **allowlist** at source, consistent with the dual-source doc. Build Phase 2 fixtures from recorded real API responses (events, pods, and Job pods from a kind cluster) before synthetic scaling. Carry `node_cpu_commit`, pod-CIDR headroom, and max-pods headroom forward as named rules in *Nodes and scheduling*.
- **Acceptance:** Replaying the retained RED snapshot (93.6% CPU commit) scores Nodes as watch or degraded. A namespace with 1,000 `PolicyViolation` events produces zero findings, and the excluded count appears in coverage.

### F13 — Overlap with the evidence lane is not decided · Medium · design

- **Reference:** `docs/observability/dual-source-kafka-triage-routing.md` §Duplicates ("`CrashLoopBackOff`, `FailedScheduling`, `ImagePullBackOff` … Vector evidence lane"); ARCHITECTURE line 79.
- **Scenario:** The monitor emits exactly those signal classes from its events and waiting-reason checks. At the workplace, one crash loop can create an incident-triage ticket through the evidence lane and also update the cluster-health issue. The plan says "do not enable a second independent ticket path for the same pilot scope" but leaves open whether the health issue counts as a second path.
- **Correction:** Decide and write it into the dual-source doc. Either (a) the health path is a separate, labelled "state lane" whose issue is a cluster summary that links to lane tickets instead of duplicating them, or (b) turn off the monitor's events check and take those signals from the evidence lane's results topic.
- **Acceptance:** With both lanes live and one crash-looping workload, the ticket count matches the documented design and the health issue links to the incident ticket.

### F14 — GitLab reconciliation by marker search is not exact · Medium · design

- **Reference:** ARCHITECTURE §Correlation and ticket policy ("reconcile by incident marker"); REVIEW Q8.
- **Scenario:** A full-text marker search can lag or miss when GitLab uses advanced search indexing, and it can partially match. After a database restore loses a recent mapping, a missed search result leads to a blind create.
- **Correction:** Put the incident ID in a scoped label (`health-incident::<id>`) and reconcile with an exact `labels=` filter plus `state=all`, not `search=`. Keep the marker in the description for humans.
- **Acceptance:** Add to E18/E20: delete the mapping row, restore from backup, and reconciliation finds the issue through the label filter with no new create.

### F15 — Update budget can starve the scheduled evening report · Medium · policy

- **Reference:** ARCHITECTURE budgets table (4 updates per cluster per 24h, 1 new issue per 24h, human closure during pilot).
- **Scenario:** A cluster that flaps in the morning spends four updates by midday, so the 16:30 report cannot post. A human closing the issue at 10:00 followed by an unrelated incident at 14:00 hits the one-new-issue limit, and the new incident is only in the report.
- **Correction:** Reserve two update slots for the scheduled reports. Show budget exhaustion and the incidents it blocked at the top of the report and send it through the existing alert route. State the closed-then-new behaviour in the runbook.
- **Acceptance:** Add to E14: four material changes before 12:00, and the 16:30 update still posts.

### F16 — Soak too short to calibrate · Medium · policy

- **Reference:** PLAN Phase 7 step 4 (72h); WORK-HANDOFF §Roll out (72h); sentinel README ("run in log-only for 1–2 weeks … every threshold is currently a guess").
- **Scenario:** 72 hours gives six reports, no real weekend, and no Monday morning. Thresholds tuned on six samples will be wrong at the workplace.
- **Correction:** Report-only costs nothing, so run it for at least 10 working days including one real weekend in B1. Keep the injected-clock tests for DST and holidays.
- **Acceptance:** The SRE signs off a labelled report set of at least 20 slots, with the false-positive rate recorded per rule.

### F17 — Per-namespace monitor count at workplace scale · Medium · work

- **Reference:** chart values (sized for one namespace of about 50 pods); REVIEW Q15; WORK-HANDOFF §Roll out step 6.
- **Scenario:** N namespaces × M clusters Deployments, each with its own Kafka client, list calls every 60s, and log streams. The patch-versus-adapter decision in Phase 1 depends on whether this model survives scale, but the plan leaves measurement to rollout.
- **Correction:** Decide in Phase 1 between per-namespace monitors and one sharded multi-namespace collector per cluster, based on a measured per-namespace API cost from B1. F11 points toward the collector model.
- **Acceptance:** B1 records list calls, bytes, and memory per namespace, and the Phase 1 decision cites them.

### F18 — Plan does not name `aks-certification` · Low · design

- **Reference:** baseline-sentinel README ("merge, don't build alongside … add one `check-baseline` step to `aks-certification`"; its `bitnami/kubectl` image no longer pulls); PLAN Phase 1 step 4 ("installed templates").
- **Scenario:** The documented direction is to extend the deployed `aks-certification` template. The plan refers only to the sentinel's standalone copy. A builder could extend the wrong one, or end up running two schedulers (the sentinel CronWorkflow runs `*/15` in UTC).
- **Correction:** Name `aks-certification` as the reuse target, record the dead image reference, and state which scheduler owns the checks.
- **Acceptance:** The Phase 1 reuse decision lists one scheduler per check family.

### F19 — DST test targets the wrong risk · Low · policy

- **Reference:** ARCHITECTURE line 126; EVIDENCE E23.
- **Scenario:** In `Europe/London`, 07:30 and 16:30 fall outside the 01:00–02:00 transition hour, so skipped or duplicated slots from DST cannot happen. The real risks are a missed run while Argo is down and a catch-up run that fires late.
- **Correction:** Keep the DST case as a cheap regression. Put the effort into `startingDeadlineSeconds` and missed-slot behaviour: one late report, or a recorded miss, never two.
- **Acceptance:** With the controller down 07:00–08:30, the report shows one clearly labelled late slot or a recorded miss.

## Answers to REVIEW.md questions

| Q | Short answer | Finding |
|---|---|---|
| 1 | Partly. It reuses checks but does not name `aks-certification`, and it adds a central scheduler. | F18 |
| 2 | Usable only after major patches. Four more storm-shaped defects need fixing. | F04–F07, F10 |
| 3 | Yes, if the agent has no Kubernetes tools. Its value then needs to be restated. | F01 |
| 4 | Per cluster, yes. Per namespace, no: tenants can reach the credential. | F11 |
| 5 | Not with pod-name keys. Snapshots make most of this unnecessary. | F02, F04, F08 |
| 6 | Unnecessary under snapshots. As designed, it does not prevent the poll loop stalling. | F02, F06 |
| 7 | Defined in prose. The number of crash points is the argument for snapshots. | F02 |
| 8 | Mostly. Use label-exact reconciliation. | F14 |
| 9 | Yes, it can hide failures: shared-services degraded and delivery critical never breach. | F09 |
| 10 | The rules are sound (evidence required, hypotheses labelled). | — |
| 11 | Not decided against the evidence lane. The monitor's default flag fails open. | F07, F13 |
| 12 | Yes in PostgreSQL. The scheduled report needs reserved budget. | F15 |
| 13 | Both are covered, but hygiene cardinality is missing and fidelity needs recorded real fixtures. | F05, F12 |
| 14 | Too short. Weekend coverage is simulated only. | F16 |
| 15 | Unknown. Measure in B1, decide in Phase 1. | F17 |
| 16 | Adequate apart from tenant credential exposure. | F11 |
| 17 | No. The report depends on transport. | F03 |
| 18 | The lab list in ARCHITECTURE is honest. Add: tenant RBAC model, existing consumers of the monitor topic, and GitLab search configuration. | — |

## Missing evidence and workplace assumptions

- The cause of the ~20,000-ticket flood. Until WORK-HANDOFF step 2 runs, the design is guarding against a guessed cause. F07 (default triage flag on) and F04 (pod churn) are plausible candidates to check first.
- Every current consumer of `k8s.namespace.findings` or equivalent workplace topics, and whether any of them read `ai_triage_required`.
- The deployed `aks-certification` template version and image at the workplace.
- Workplace tenancy: whether namespace admins can read Secrets in their own namespaces (F11).
- GitLab edition and search backend, which decides whether marker search is safe (F14).
- Whether a Kafka topic per cluster is allowed by the workplace Confluent governance model (plan already flags this).
- The measured per-namespace API cost of the monitor. There is none yet (F17).

## Plan-package notes

- This file makes the pack seven documents. EVIDENCE §Plan-package checks says "all six Markdown documents"; update the count when the pack is next validated.
- All eleven distinct relative link targets in the six original documents resolve (checked 2026-09-15).
- Record these findings and the owner's disposition in the [REVIEW.md](REVIEW.md) register. Owner disposition is not filled in here.
