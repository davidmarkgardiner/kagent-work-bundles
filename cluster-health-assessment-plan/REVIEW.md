# Independent critique response and decision register

Revision 2 response, 2026-09-15. The original [REVIEW-FEEDBACK.md](REVIEW-FEEDBACK.md) is preserved unchanged.

## Review status

| Field | Current value |
|---|---|
| Reviewed revision | Original six-document working copy, 2026-09-15 |
| Reviewer | Claude, Opus 5, independent of the plan author |
| Original verdict | REVISE BEFORE BUILD |
| Author response | Revision 2, snapshot-based B1–B4 plan |
| Follow-up reviewer verdict | PENDING |
| Owner disposition | PENDING for all findings |
| Owner build decision | PENDING; no implementation authorised by this response |
| Runtime evidence | NOT RUN |

The findings below are addressed in the proposed design, not verified fixes. Critical/high findings still require follow-up review and their stated implementation tests. The next build decision can be limited to B1; it need not authorise the later services or side effects.

## Response to all findings

| Finding | Author response in revision 2 | Acceptance evidence | Owner disposition |
|---|---|---|---|
| F01 Critical | Accept. New Agent has zero tools and no sub-agents. Future validator change explicitly allows empty evidence-only tools and rejects all additions. Agent value is measured; B3 optional | E22, G3 | Pending |
| F02 Critical | Accept snapshots. Remove per-finding transport, historical spool, intake outbox. Preserve caveats: top-N omission cannot resolve; transient history can be lost; compaction is asynchronous | E15, E16, E20, E21, E29 | Pending |
| F03 High | Accept. B1 local report precedes broker/database/agent work; four separately estimated builds replace the combined estimate | E01, G1 | Pending |
| F04 Critical | Accept. Rekey within the monitor/adapter before retained state, using workload and symptom family; collapse scheduling symptoms | E05 | Pending |
| F05 Critical | Accept. Per-container resource-spec findings disabled; namespace hygiene counts have no per-container state | E13 | Pending |
| F06 High | Accept. No broker in B1; B2 publisher independent of polling with latest-only bounded slot and Kafka queue | E15 | Pending |
| F07 High | Accept. Exact false required, invalid booleans rejected, no triage flags in snapshot contract, suppression errors explicit; inventory consumers before B2/work | E04, E27 | Pending |
| F08 High | Accept through snapshot identity `(cluster, generation, sequence)`, not upstream finding ID. Retries preserve identity; same-ID checksum conflict quarantined | E16 | Pending |
| F09 High | Accept. Domain outcomes control breach/recovery, display mean never gates. Add impact denominators and exhaustive outcome tests | E08 | Pending |
| F10 Medium | Accept. State-write/pruning failures visible; trend coverage partial; active group identities cannot cycle through eviction and rediscovery | E03, E13 | Pending |
| F11 High | Accept. Platform-owned collector/state/publisher, tenant read Roles, no tenant-accessible producer credential, enforced namespace allowlist | E11 | Pending |
| F12 Medium | Accept. Real API fixtures, event allowlist with excluded counts, named CPU-commit and pod-capacity headroom rules | E02, E28 | Pending |
| F13 Medium | Accept option A. State lane owns a labelled cluster summary linking existing incidents. Explicit coexistence count is one incident plus one summary, not one total | E30; routing-policy note | Pending |
| F14 Medium | Accept exact labels and all-state pagination; retain fail-closed ambiguous-write policy. Cluster label supports mapping-loss discovery; label filtering is not uniqueness | E18, E20 | Pending |
| F15 Medium | Accept reserved morning/evening update slots, separate unscheduled budget, visible blocked changes, closed-then-new runbook. Clarify DST rolling-window exception | E14, E19, E23 | Pending |
| F16 Medium | Accept 10 working days, real weekend, and at least 20 labelled weekday slots. Report-only resource/operator cost is measured | E24 | Pending |
| F17 Medium | Accept B1 cost measurement and a process/shard choice at B2 entry. Platform namespace is mandatory regardless of the choice | G1, G2 sizing record | Pending |
| F18 Low | Accept. Name `aks-certification`, inspect obsolete image reference, and record a single collection scheduler and report-slot owner | G1 inventory | Pending |
| F19 Low | Accept. Prioritise missed-slot/grace-period behaviour. Keep DST regression but do not imply 07:30/16:30 is in the skipped hour | E23 | Pending |

## Additional qualifications to the critique

Snapshots reduce transport complexity but do not remove every correctness boundary:

- Bounded detail requires explicit aggregate and group-membership completeness. A group falling out of top-N is not recovery.
- A compacted topic retains latest keyed state eventually, but a restarting consumer can read many historical snapshots. Catch-up coalescing and a side-effect barrier remain necessary.
- A fresh snapshot rebuilds current health after restore. It cannot reconstruct admission spend, GitLab operations, accepted history, or old reports.
- A tool-free agent can cite a valid reference while misinterpreting it. Static reference checking needs fixture/human entailment review.
- Label-exact GitLab queries improve identity lookup but provide no atomic uniqueness. Removed labels or unknown permissions require reconciliation, not another create.
- Ten working days yields a useful calibration sample, not proof of production accuracy. Report-only operation has infrastructure and operator cost.

These qualifications preserve the smaller design without overstating its guarantees.

## Follow-up reviewer prompt

Review revision 2 of [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md), [PLAN.md](PLAN.md), [EVIDENCE.md](EVIDENCE.md), and [WORK-HANDOFF.md](WORK-HANDOFF.md), plus the proposed state-lane section in [dual-source routing](../../docs/observability/dual-source-kafka-triage-routing.md). Compare them with the original feedback.

Return READY FOR B1 DECISION, REVISE BEFORE BUILD, or REJECT DESIGN. List each unresolved finding, exact reference, failure scenario, correction, and required test. Separately assess whether B2–B4 are specified enough for later decisions. Do not mark an implementation defect fixed because its correction appears in a plan.

Focus on local report usefulness before infrastructure, snapshot completeness/order/catch-up, monitor state and configuration failure modes, platform-versus-tenant isolation, domain gates, tool-free agent value, state-lane coexistence, exact-label reconciliation, reserved report slots, and achievable estimates. Challenge components that remain unnecessary.

Do not implement, deploy, publish, open issues, or contact anyone during the review. Keep the owner's build decision separate from the review verdict.
