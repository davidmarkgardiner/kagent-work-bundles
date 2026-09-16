# Cluster health assessment: homelab build and workplace transfer

Status: revision 3 is the last live single-cluster homelab MVP. Revision 6 is a workplace-ready source bundle verified offline. Its runtime images have not been built or pushed, and its manifests have not been deployed. It retains the exact Alloy/Vector namespace scope, adapts the Fox Go collector to state-only operation, emits one bounded health record per UTC date through Vector/Kafka, invokes a read-only AKS-MCP investigation only when unhealthy, and includes an explicitly gated single-summary GitLab writer. The earlier two-API-server proof is retained but quiesced. Real image, Kafka, agent, GitLab, controlled-fault, elapsed-soak, independent-review, and workplace sign-off evidence remain promotion gates.

Prepared and revised: 2026-09-16.

## Intended outcome

Produce a useful morning and evening cluster health report on one worker before adding transport, agents, or tickets. Later builds send bounded snapshots to a separate agentic cluster, optionally add evidence-only agent analysis, and maintain one active cluster-health summary issue.

The motivating incident produced approximately 20,000 tickets. Its workplace cause remains unverified. Test plausible amplification mechanisms without creating thousands of real issues.

## Read this pack

1. [Build plan](PLAN.md): four separately gated builds and their estimates.
2. [Architecture](ARCHITECTURE.md): snapshot contract, domain-health gates, identity, and reporting policy.
3. [Evidence record](EVIDENCE.md): build-specific acceptance tests and current B1 receipts.
4. [Original independent feedback](REVIEW-FEEDBACK.md): the critic's unchanged REVISE BEFORE BUILD verdict.
5. [Review response and register](REVIEW.md): response to all 19 findings and remaining decisions.
6. [Workplace handoff](WORK-HANDOFF.md): configuration, ownership, and workplace proof requirements.
7. [Triage rollout pause summary](TRIAGE-ROLLOUT-PAUSE-SUMMARY.md): the decision to suspend the high-volume rollout, restart conditions, the lower-impact replacement, and an unsent team-message draft.

## What changed after review

- B1 delivers a worker-local report using audited `aks-certification` checks and corrected namespace aggregates. It requires no Kafka, PostgreSQL, agent, GitLab, or second cluster.
- B2 transfers complete bounded state snapshots. Per-finding deltas, a historical publication spool, and an intake outbox are deferred.
- Any required domain degraded or critical can trigger a breach. The weighted score is a display value only.
- B3 uses a new Agent with zero tools and zero sub-agents. Reusing the existing orchestrator would risk inspecting the agentic cluster instead of the worker.
- Collectors and later Kafka credentials live in a platform-owned namespace. Tenant namespace administrators cannot obtain a cluster-wide producer identity.
- B4 reserves scheduled-report update slots and reconciles GitLab issues through exact labels.

Reuse [the existing sentinel's checks](../cluster-health-baseline-sentinel/README.md) through the audited `aks-certification` path. Do not reuse the old orchestrator tool list or create a second collection scheduler.

## Current implementation scope

The revision-3 [B1 implementation](b1/README.md) is running on one home-lab worker in a platform-owned namespace. It produces five-minute immutable snapshots, weekday morning/evening reports, Prometheus metrics, and a dashboard artifact. The [Fox mesh](fox-mesh/README.md) adds a separately deployable namespace sensor layer; B1 remains the only cluster snapshot/gate owner. Revision 6 disables Fox per-finding publication and gives Kafka credentials only to a Vector sidecar publishing the bounded daily `cluster-health.alert.v1` contract. No raw Fox finding is wired to Argo or a ticket writer.

The [B2 implementation](b2/README.md) transfers current snapshots over authenticated HTTPS into PostgreSQL on a second Kubernetes API server, without a shared filesystem or worker credential in the cage. The historical [B3 boundary](b3/README.md) prepares cited evidence with zero Kubernetes tools and passed one temporary model-route proof. Revision 6 instead supplies the daily unhealthy payload to a tightly instructed read-only Agent whose AKS-MCP identity must be independently constrained to the named worker target. A separate fixed adapter, disabled by default, reconciles exactly one labelled SRE GitLab issue without giving the Agent a token. Start workplace adoption at the [deployment bundle](workplace-bundle/README.md). See the [daily/GitLab offline receipt](evidence/2026-09-16-daily-gitlab-bundle-offline.md), [accelerated live receipt](evidence/2026-09-15-accelerated-lab.md), [Fox mesh offline receipt](evidence/2026-09-16-fox-mesh-offline.md), [model proof](evidence/2026-09-15-model-proof.md), and [operator runbook](RUNBOOK.md).

The accelerated replay qualifies 20 slot identities across a weekend and DST change, but deliberately does not claim that ten real working days elapsed. The independent verdict still applies to revision 1; revisions 2–4 and the implementation have not passed follow-up critique. A Claude review attempt and Kimi fallback both failed operationally during the revision-4 build; the failure-only receipt is retained in [`fox-mesh/peer-review-receipt.json`](fox-mesh/peer-review-receipt.json).

The active lab now uses the [single-cluster overlay](single-cluster/README.md). It models worker and manager roles as separate namespaces on the same API server while preserving the eventual cross-cluster contract. See the [live single-cluster receipt](evidence/2026-09-15-single-cluster.md).
