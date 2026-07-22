# Front Sheet — Cluster Health Baseline Sentinel

| | |
|---|---|
| **Ask** | Catch cluster-scope problems namespace-routed triage cannot, and hand them to an agent that investigates and reports |
| **Proposal** | **Add one `check-baseline` step to the existing `aks-certification` workflow** — not a new system |
| **Status** | Agent path proven end-to-end on RED (homelab kind cluster), 2026-07-15. Stood down after proof. |
| **Not proven** | The merge itself (patch written against the live contract, not yet run), multi-node, Alertmanager route, storm detector, fault injection, all cross-cluster paths |
| **Patch** | `examples/aks-certification-baseline-patch.yaml` + `examples/cronworkflow-certification.yaml` |
| **Reference impl** | `agents/cluster-health-sentinel/` (9 manifests + README) — the standalone version, proven, now the source of the pieces being merged |
| **Design history** | `WORK-CLUSTER-HEALTH-SENTINEL-PLAN.md` (§10 codex review, §11 what the cluster taught us) |
| **Risk posture** | Read-only throughout. No auto-remediation. Reporting defaults to `log-only`. |

## The proposal in one paragraph

`aks-certification` already runs api-server / dns / networking / storage /
critical-pods / node-health / rbac / secrets and emits one structured JSON
report. Every check is **pass/fail on current state**, so it detects *broken* and
is blind to *drifting* — it would certify RED healthy today, at 93.6% CPU commit
with no scheduling headroom left. Add one `check-baseline` step emitting the same
contract, then escalate to the agent when **any check fails or the baseline
moves**. Same workflow: run on provision it's a certification gate, run every 15
minutes it's a health monitor.

## The gap, in one picture

```
Namespace-routed triage (today)          Cluster-scope sentinel (this)
────────────────────────────────         ──────────────────────────────
warning event                            periodic whole-cluster snapshot
  → filter by namespace                    → baseline drift detection
  → namespace specialist agent             → generic orchestrator agent
  → "pod X is unhealthy"                   → "node pressure; these 10
                                              namespaces are downstream"

Good when the namespace IS the problem.  Good when it ISN'T.
Cannot see shared causes.                Does not replace the above.
```

## Why not just LGTM

LGTM alerts when **one metric crosses one line**. This detects **drift in a
composite picture**, where no single metric may have breached. Prior analysis
(`agentic-triage-smoke-tests/LGTM-METRICS-ONLY-COVERAGE.md`) puts metrics-only
triage coverage at 35–45%. Keep LGTM for time series and history; this is the
"what does it mean" layer above it.

Evidence from RED, which makes the case better than argument: **858 of 859
warning events were Kyverno `PolicyViolation`** from Audit-only policies that
enforce nothing. Any threshold over raw event volume there is meaningless.
Excluding it at source took the signal from 1078 to 2.

## Proven chain

```
collector CronJob → node_cpu_commit 93.6% breach → webhook HTTP 200
  → sensor → workflow → orchestrator agent → GitLab issue #444
```

Agent CRD reached `Accepted=True` / `Ready=True`, confirming Agent-type tool
refs resolve on the installed kagent CRD.

## The finding that decides fleet design

`kagent-tools` uses an **in-cluster ServiceAccount, no kubeconfig**. Its tools
always query the cluster they run in. A central orchestrator reasoning about a
worker's snapshot would silently drill into the *management* cluster instead —
wrong facts, no error. **So the orchestrator runs where its tools point**, and
only the verdict (~2 KB) crosses the cluster boundary, not the snapshot (~200 KB).

## Headline lesson for the work rollout

Six defects. **Zero** were caught by design review or by 44 passing offline unit
tests — including a remote code execution path and a bug that made every
advertised time window a no-op. Four were found by real cluster data, one by
testing a hunch, one by checking a teammate's number that disagreed with ours.

The tests passed because they asserted our assumptions back to us. Budget for
cluster time, not just review time.

## Before this goes anywhere near work

1. The EventSource webhook is **unauthenticated** — NetworkPolicy at minimum.
2. Nothing watches the watcher — if the CronJob stops, silence looks like health.
3. Baselines are guesses. Run `REPORT_MODE=log-only` for 1–2 weeks first.
4. `bitnami/kubectl` is dead — **23 other YAML manifests in this repo** still use
   it, including `namespace-onboarding`, `app-onboarding`, `aso-provisioning`,
   the canary templates and kro-stack certification. They will ImagePullBackOff
   on first run.
5. kagent agents inherit a **100m CPU default** each. RED runs 31 agents = 3830m,
   51% of the cluster. At fleet scale that tax is real.
