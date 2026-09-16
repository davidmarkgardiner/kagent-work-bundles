# Build the homelab assessment and prepare workplace transfer

Revision 3. The independent review returned REVISE BEFORE BUILD. The owner authorised execution and then requested accelerated completion on 2026-09-15. The homelab MVP is running end to end through a local summary ledger; promotion gates requiring elapsed time, SRE/reviewer acceptance, a live model Agent, or external GitLab remain open.

## Scope, owners, and estimates

Build a useful local report first. Add transport, optional agent analysis, and sandbox ticketing as separate decisions. Estimates include engineering work but exclude review turnaround, infrastructure procurement, and calendar time for calibration. Re-estimate at every gate; the earlier combined 10–15 day estimate is withdrawn.

| Role | Responsibility |
|---|---|
| Build owner | Reuse, minimal monitor patch, packaging, and receipts |
| Platform owner | Host capacity, cluster/namespace permissions, Kafka, storage, and restore |
| SRE operator | Rule labels, accepted baseline, report usefulness, and daily operation |
| Independent reviewer | Plan revision and evidence assessment |
| Workplace owner | Environment mapping, approved destinations, and rollout scope |

Review dispositions are recorded in [REVIEW.md](REVIEW.md). The owner's 2026-09-15 instruction authorised B1 execution on the home-lab worker. It did not waive G1 or authorise B2-B4.

## B1: produce a useful report on one worker

Execution status: LAB IMPLEMENTATION COMPLETE; PROMOTION GATE OPEN. The local collector, immutable snapshots, scheduled reports, metrics endpoint, dashboard artifact, least-privilege pilot bindings, fixtures, policy tests, 20,000-observation aggregation test, and accelerated 20-slot/DST replay are built and running. See [the B1 runbook](b1/README.md), [initial receipt](b1/evidence/2026-09-15-live-smoke.md), and [accelerated receipt](evidence/2026-09-15-accelerated-lab.md). Real elapsed calibration, SRE usefulness acceptance, optional metrics-datasource hookup, and remaining fault fixtures are not complete.

Estimate: 5–8 engineering days for the corrected local prototype, plus at least 10 working days of labelled report-only calibration spanning a real weekend. Target the first partial sentinel-based report in 1–2 days if reusable infrastructure is available. Namespace coverage remains explicitly incomplete until its adapter passes the required checks.

1. Inspect host capacity and one worker's actual Kubernetes, Argo, Flux, metrics, and storage configuration. Record private identities outside this public pack.
2. Identify the deployed `aks-certification` version, image digests, Flux owner, and scheduler. Record one owner per check family. Replace obsolete images through a reviewed build change.
3. Reuse passive certification checks and `check-baseline`. Include node CPU commit, pod-CIDR headroom where valid, and max-pods headroom. Exclude provisioning mutations and secret inspection.
4. Write the first bounded immutable snapshot and morning/evening report as a local ConfigMap/artifact. Publish metrics for an existing Grafana view. Do not provision Kafka, PostgreSQL, agent, or GitLab dependencies.
5. Add the corrected namespace-monitor aggregate adapter in a platform-owned namespace. It must operate without constructing a Kafka client. Separate watched namespace from state namespace and use read-only RoleBindings.
6. Apply the correction list in [ARCHITECTURE.md](ARCHITECTURE.md): workload/symptom keys, collapsed scheduling checks, disabled per-container hygiene findings, event allowlist, strict configuration, explicit coverage, bounded state, and corrected temporal checks.
7. Build fixtures from sanitised real Kubernetes API responses before scaling synthetic data. Cover successful Job pods, real timestamp shapes, old/new errors, 50-replica pod churn, 1,000 containers without limits, and 1,000 excluded policy events.
8. Implement domain-based admission/recovery and the optional display score. Validate all 1,024 domain combinations plus unknown coverage. Record absolute headroom rules separately from accepted historical baselines.
9. Measure API calls, bytes, memory, poll duration, state growth, and operator time per namespace. Use the results to decide per-namespace processes versus a sharded collector before B2. Record assumptions for projected fleet size.
10. Collect at least 20 labelled weekday report slots over 10 working days and one real weekend. Record false positives per rule and missed/late slots. Keep operational alerts monitored.

Deliverables: local report and Grafana view, audited collection scheduler, corrected adapter, pinned source/image references, labelled fixtures, coverage and rule results, resource measurements, and B2 architecture decision.

Gate G1: SRE can review a useful report before any new Kafka topic exists; mandatory B1 evidence passes; a labelled calibration set and accepted scope exist. No model calls or ticket writes. If the namespace patch proves too large, deliver the sentinel report with that coverage marked missing and revise the estimate rather than claiming B1 complete.

## B2: transfer snapshots to a separate agentic cluster

Execution status: LAB IMPLEMENTATION COMPLETE WITH AN APPROVED ARCHITECTURE DEVIATION. The active deployment now uses separate worker and manager namespaces on the single `red` API server. Its HTTPS intake is ClusterIP-only and retains HMAC identity binding, bounded current-state storage, partial-state protection, and restore semantics. The earlier second-API-server proof is retained as evidence but its workloads are quiesced. The active topology does not prove independent cluster or physical failure domains, Kafka, or a second real worker.

Estimate: 3–5 engineering days after G1 and usable central infrastructure. Additional cluster provisioning is estimated separately.

1. Freeze the bounded snapshot schema and source identity model. Implement aggregate completeness, top-N truncation, generation/sequence, checksum, and snapshot age handling.
2. Add one independent publisher per worker. It reads the latest saved snapshot without blocking collection. Bound both the replaceable slot and Kafka internal queue; no historical spool or per-finding deltas.
3. Configure a platform-only producer credential and approved per-cluster compacted topics. Verify tenant credential isolation, namespace allowlists, TLS/authentication, broker-address reachability, and all topic consumers.
4. Deploy a small central consumer and PostgreSQL latest-assessment/report store. Apply atomic newer-snapshot replacement. Keep partial latest attempts separate from the last complete view and its age.
5. Implement a catch-up barrier that coalesces historical records with side effects disabled. A fresh complete snapshot is required before future automation can resume.
6. Stop broker access for 30 minutes with at least 100 active local findings. Verify zero publisher-induced monitor restarts, stable polling cost, stale central coverage, and convergence after reconnect.
7. Restore an old central backup and verify health convergence from the next complete snapshot. Record that historical reports and baselines require backup restore, not snapshot reconstruction.
8. Move scheduled report publication centrally with a slot-ownership cutover. Test short and long Argo controller outages and recorded misses.
9. Verify transport between distinct worker and agentic API servers. Test a second simulated identity, then add a second real worker before claiming multi-worker network isolation.

Deliverables: schema, publisher, topic/identity mapping, central store, central reports, cross-cluster receipt, outage/restore tests, and sizing revision.

Gate G2: reports agree across the boundary, partial/truncated data cannot cause false recovery, tenant and cross-cluster isolation pass, and current state converges without replaying historical side effects. No agents or GitLab required.

## B3: evaluate bounded evidence-only analysis

Execution status: MODEL HARNESS PROOF COMPLETE; KAGENT/VALUE GATE OPEN. A cage CronJob with no Kubernetes token, tools, or delegation reads only the stored snapshot. A temporary model route proved one real call, and a first semantically weak result drove stricter deterministic severity/summary and claim-ID validation. The accepted proof persisted warning severity, unknown root layer, six exact supplied claims, and zero tool calls. The recurring job was returned to deterministic mode and the temporary model credential/route removed. A validated empty-tool Agent template and repository validator rule are included. G3 remains open because the kagent runtime is not installed in the cage and SRE value is unmeasured.

Estimate: 2–4 engineering days after G2. This build is optional if the deterministic report already meets SRE needs. B4 can use deterministic reports without B3.

1. Create a new Agent with an empty tool list and no delegated agents. Do not reuse the sentinel orchestrator. Inspect the installed Agent schema and effective runtime tool list.
2. Extend `scripts/validate-agent-cr.py` with an evidence-only label rule. Permit empty tools for that mode and reject any tool or delegation entry. Run `scripts/tests/smoke-helpers.sh` after this future helper change.
3. Implement central request and budget reservations for material assessment revisions. Reconcile admitted requests to deterministic Workflow names. This is a bounded request ledger, not a per-finding ingestion outbox.
4. Fetch and verify the pinned assessment in Argo, then supply it and approved runbook excerpts as data to the tool-free agent. Use distinct A2A context for each independent investigation.
5. Test worker-only namespace evidence. The agent must make zero tool calls and distinguish supplied facts from unavailable detail; invalid references and unsupported claims fail evaluation.
6. Test instruction-like log content, invalid output, model timeout, workflow retry, and an ambiguous successful model call. Bound retries and keep deterministic reports available.
7. Compare SRE review time and explanation usefulness with the original report. Record calls, complete request bytes, tokens, latency, and limitations. Drop the agent stage if it adds little value.

Deliverables: new Agent/Workflow definitions, validator changes, bounded request ledger, A2A receipts, and a measured value decision.

Gate G3: zero tool calls, no agentic-cluster facts substituted for worker facts, evidence-grounded output, durable budgets, and a positive SRE value decision. Reuse `scripts/kagent-verify-agent.sh` and `scripts/kagent-a2a-invoke.sh` where appropriate; do not bypass the new empty-tool validation rule. Group conditionally skipped Argo steps in a gated sub-template.

## B4: prove a controlled sandbox summary issue

Execution status: LOCAL LEDGER COMPLETE; EXTERNAL DELIVERY DISABLED. Create, unchanged replay, material update, and human-closed conflict behavior are proven against one stable cluster summary key. The CronJob is suspended and writes zero external issues. G4 remains open until an authorised GitLab sandbox proves API reconciliation and real issue reuse.

Estimate: 3–5 engineering days after G2 and a separately authorised sandbox project. B3 is optional. Workplace production rollout is outside this estimate.

1. Add a dedicated writer credential and central operation ledger. Reserve per-cluster claims and budgets atomically before external writes.
2. Implement stable cluster/incident labels and exact label-filter reconciliation, including all states, full pagination, and exact returned-label checks. Keep a human-readable marker too.
3. Create one summary and update the same issue. Link existing incident tickets through the state-lane mapping; do not create duplicate workload tickets.
4. Reserve scheduled-report update slots separately from unscheduled updates. Test four morning changes, a delivered 16:30 report, and the displayed blocked-change count.
5. Simulate GitLab acceptance followed by connection loss, process crash, old database restore, lost mapping, removed labels, and multiple matching issues. Uncertain outcomes stop blind creation.
6. Test human closure followed by a new fault inside the create window. The report and operational alert remain visible; no replacement loop starts.
7. Stress local aggregation with 20,000 raw observations, then verify bounded snapshot publication. Stress central catch-up with historical/duplicate snapshots while dispatch is disabled. Do not implement a production per-finding delta route to run the old replay test.
8. Prove coexistence with the existing evidence lane: one incident issue and one linked health summary at most. If the legacy writer lacks effective limits, do not enable coexistence.
9. Run an authorised limited-ticketing trial, observe real issue IDs/updates, and rehearse stop-write, restore, and scoped rollback procedures.

Deliverables: writer ledger, label reconciliation, actual issue receipts, storm counts, reserved-slot tests, operator runbook, and portable package.

Gate G4: real sandbox delivery/reuse, bounded writes during failures, controlled coexistence, and an operator who can stop and recover the service. A mock API does not establish actual GitLab behaviour.

## Package the workplace handoff

After each successful build, freeze the tested scope and update [EVIDENCE.md](EVIDENCE.md). After G4, package image digests, schemas, rule versions, minimal monitor patches, store migrations, RBAC, overlays, fixtures, verification scripts, and runbooks. An independent reviewer assesses the achieved evidence and explicit gaps before workplace evaluation.

All permanent delivery follows the existing GitOps path. Future live faults use dedicated fixture namespaces and a separate test identity; reuse `scripts/kagent-e2e-fault-test.sh` when its safeguards fit. Simulate pressure when a real node fault would affect unrelated workloads. Cleanup preserves user resources and checks recovery.

## Deferred scope

Do not build a local historical spool, per-finding transport, intake outbox, or lossless delta-replay system unless a later reviewed requirement needs them. Do not make 20,000-record stress, extra API servers, or writer/agent infrastructure prerequisites for the first local report. No automatic remediation, new observability stack, or shared cross-cluster filesystem is included.
