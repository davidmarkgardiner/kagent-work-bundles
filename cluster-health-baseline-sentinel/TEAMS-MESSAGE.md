# Teams message — paste-ready

Purpose: socialise the idea, invite better ones, before we cut a GitLab ticket.

---

**Adding a baseline check to `aks-certification` — would welcome a sanity check, or a better idea** 🩺

**The gap:** our triage routing is namespace-keyed. A warning event fires, the sensor routes it to the agent that owns that namespace. Great when that namespace *is* the problem. Useless when node pressure / IP exhaustion / a knackered addon shows up as symptoms across ten namespaces at once — every agent investigates its own slice and nobody sees the shared cause. And nothing catches things that are *brewing* but haven't broken yet, because there's no event to route.

**Good news: we've mostly built this already.** `aks-certification` (been deployed on my homelab 169 days) already runs real health checks — api-server, dns, networking, storage, critical-pods, node-health, rbac, secrets — each emitting structured JSON that `generate-report` assembles into one document. That's ~70% of a cluster-health snapshot, and dns/networking/rbac/secrets are four checks I wouldn't have thought to include.

**What it can't do is drift.** Every check is pass/fail on current state. A node that's Ready passes — even at **93.6% CPU commit with no scheduling headroom left**. That's my homelab right now: all nodes Ready, zero crashloops, everything bound, every check green. `aks-certification` would certify it healthy. It's not broken; it's one deployment away from broken. That's precisely the case we said we wanted to catch.

Same blind spot on noise: certification doesn't look at events at all. In one window on that cluster, **858 of 859 warning events were Kyverno PolicyViolation from Audit-only policies that enforce nothing** — and Kyverno double-counts, emitting a duplicate event against the ClusterPolicy object for every real violation (measured at exactly 50.0% of 1192 events). Any threshold on raw event volume there is meaningless.

**Proposal — one more check, not a parallel system.** Add `check-baseline` to the existing DAG next to the others, emitting the same contract (`/tmp/result.json` → `outputs.parameters.result`). Its result joins the same report. Then a final step: **if any check failed, or the baseline moved → hand the whole report to an agent**, which investigates with its tools and returns a verdict. The agent gets certification results *and* drift in one document, which is a much richer prompt than either half — "DNS is fine, nodes Ready, but you're at 93.6% and it moved."

Nice property that falls out: same workflow, the *schedule* decides the question. Run on provision → certification gate. Run every 15 min → health monitor.

**Proved the agent half end-to-end on the homelab.** Caught the 93.6% commit, classified it node-pressure, scoped blast radius, and — unprompted — used its tools to check some alarming-looking restart counts (kindnet 75, metallb 62), found they were 47 days old, and correctly dismissed them as chronic rather than acute. Opened a GitLab issue. The patch + CronWorkflow are written against the live template's actual contract, not a guess.

**Two things worth knowing before anyone leans on this:**
- **`aks-certification` cannot run today.** Every check uses `bitnami/kubectl:latest`; Bitnami retired their public catalog, so it ImagePullBackOffs. **23 YAML manifests in the repo have the same dead reference** — including namespace-onboarding, app-onboarding, aso-provisioning and the canary templates. That sweep is realistically the first job.
- **`uk8s-cluster-certification`'s aggregator is a stub.** `total_checks = 0` hardcoded, comment says "would be passed as parameters in real implementation", so `certified` evaluates to False every time — it always reports NOT CERTIFIED 0.0% regardless of cluster state. The docs record "✓ aggregate-results: Succeeded", which is the workflow *phase*, not the check working.

**The ask** — is this the right shape, or does something off-the-shelf already do it? Robusta, Komodor, k8sgpt, Mimir recording rules, Grafana Alerting? **I'd genuinely rather lift and shift than maintain ours.** And if you reckon the framing's wrong, say that first — more useful than agreeing with me.

Write-up: `work-agent-bundles/cluster-health-baseline-sentinel/` — start at README.md, patch is in `examples/`. There's also a REVERSE-PROMPT.md if you'd rather design your own answer before reading mine; the constraints in it are worth a skim either way, a few are non-obvious and cost me a day each.

Ticket once we've got rough agreement on direction.

---

## Shorter variant, if the above is too long for chat

**Adding a baseline check to `aks-certification` — sanity check please** 🩺

**Gap:** our triage routing is namespace-keyed — event fires, goes to the agent that owns that namespace. Great when that namespace *is* the problem. Useless when node pressure or IP exhaustion shows up as symptoms across ten namespaces and nobody sees the shared cause. And nothing catches what's *brewing* but hasn't broken, because there's no event to route.

**Turns out we've mostly built this already.** `aks-certification` runs real checks — api-server, dns, networking, storage, critical-pods, node-health, rbac, secrets — and emits one structured JSON report. That's most of the way there, and four of those checks are ones I'd not have thought to add.

**What it can't do is drift.** Every check is pass/fail on current state, so a Ready node passes — even at 93.6% CPU commit with no headroom left. That's real: it's my homelab right now, and `aks-certification` would certify it healthy today. Nothing's broken. It's one deployment away from broken.

**Proposal — one more check, not a new system.** Add `check-baseline` to the existing DAG, emitting the same contract every other check already does. Result joins the same report. Then: if any check fails **or** the baseline moved → hand the whole report to an agent, which investigates with its tools and comes back with a verdict. Nice property — same workflow, run on provision it's a certification gate, run every 15 min it's a health monitor.

Proved the agent half end-to-end on the homelab: caught the 93.6% commit, classified it, scoped blast radius, opened a GitLab issue. Patch + CronWorkflow written against the live template contract.

**Two things to flag:**
- `aks-certification` uses `bitnami/kubectl:latest`, which no longer pulls (Bitnami retired their public catalog). **It can't run today.** 23 YAML manifests in the repo have the same problem — that sweep is the actual first job.
- `uk8s-cluster-certification`'s aggregator is a stub — hardcoded zeros, always reports NOT CERTIFIED 0.0%. Worth knowing before anyone relies on it.

**Ask:** sane? Or does something off-the-shelf do this — Robusta / Komodor / k8sgpt / Mimir rules? Genuinely happier to lift and shift than maintain ours. Write-up + patch: `work-agent-bundles/cluster-health-baseline-sentinel/`. Ticket once we agree direction.
