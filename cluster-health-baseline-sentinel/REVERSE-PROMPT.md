# Reverse Prompt — solve this independently

**Purpose:** hand this to a separate team or agent and let them design their own
answer. We have one working implementation; we want to know whether it is the
right shape, or whether something better already exists that we should lift and
shift instead of building.

**How to use it:** everything above the `---SOLUTION BOUNDARY---` line is the
brief. Read that, design your answer, write it down. Only then read below the
line to see what we did. If you read ours first you will anchor to it, and the
whole point of this exercise is lost.

---

## The brief

```text
You are designing cluster-health detection and investigation for a Kubernetes
platform team running kagent (agentic SRE) across a management cluster and
multiple AKS worker clusters.

THE PROBLEM

Alert routing today is namespace-keyed. Argo Events sensors filter Kubernetes
warning events by involvedObject.namespace and trigger a workflow that hands the
event to the kagent agent that owns that namespace. It works well when the
failing namespace is the problem.

It fails for anything cluster-scope or cross-cutting:
  - node pressure, NotReady nodes, node-level resource exhaustion
  - pod scheduling failures and unschedulable backlog
  - IP exhaustion (Azure CNI subnet depletion, pods-per-node limits)
  - core addon degradation (CoreDNS, CNI, kube-proxy, metrics-server, cert-manager)
  - control-plane / API server latency
  - slow-brewing trends: restart-rate creep, eviction waves, PVCs filling

These present as APPLICATION symptoms in many namespaces at once. Each namespace
agent then investigates its own slice and none of them sees the shared cause. We
cannot route to a specialist because we do not know the issue class up front —
that is the entire difficulty.

WHAT WE WANT

Some process that periodically establishes whether a cluster is within its
normal baseline. If a cluster drifts off baseline, that signal should reach an
agent. The agent should then use every tool at its disposal — Kubernetes
read-only tools, network tools, AKS-MCP, GitLab, the knowledge base, other
agents — to investigate: what is going on, is this a known/recurring problem,
what is its history, and what should we do about it. It comes back with a
report. If the report concludes the baseline itself was wrong, we want to be
able to correct the baseline.

We want to catch things that are already broken AND things that are brewing.

WHAT WE ALREADY HAVE (candidates for lift-and-shift — please check these first)

  *** START HERE — this is the most important item in the brief ***

  - `aks-certification`, an Argo WorkflowTemplate deployed and running. It ALREADY
    performs live health checks: api-server, dns, networking, storage,
    critical-pods, node-health, rbac, secrets. Each emits structured JSON
    ({"check": "...", "status": "passed|failed", "details": []}) written to
    /tmp/result.json and exposed as an output parameter; a generate-report step
    assembles them into a single JSON document. It is parameterised by
    cluster-name, so it is already shaped for remote targets.
    Location: kubectl -n argo-events get workflowtemplate aks-certification
    KNOWN ISSUES: it uses bitnami/kubectl:latest on every check, which no longer
    pulls, so it cannot currently run. It is on-demand — there is no CronWorkflow.
    THE KEY LIMITATION: every check is pass/fail on CURRENT STATE. A node that is
    Ready passes, even at 93.6% CPU commit with no scheduling headroom left. It
    detects BROKEN. It cannot detect DRIFTING or BREWING. It also does not look
    at events at all.

  - `uk8s-cluster-certification` (infra/kro-stack/certification/): a 13-section
    config-conformance workflow. Be aware its aggregate-results step is a STUB —
    total_checks is hardcoded to 0 and `certified` therefore always evaluates
    False, so it reports NOT CERTIFIED 0.0% regardless of cluster state. Do not
    assume it works because the workflow phase says Succeeded.

  - Argo Events + Argo Workflows, already wired to kagent via A2A
  - kagent agents (kagent.dev/v1alpha2) with MCP tools via a `kagent-tool-server`
    RemoteMCPServer; agents can also be given other AGENTS as tools
  - agentgateway in front of the agents, with an existing worker→management A2A
    escalation route (/a2a/fleet/*)
  - a managed LGTM stack (Loki/Grafana/Tempo/Mimir)
  - GitLab, with an MCP integration
  - AKS-MCP: provides `call_kubectl` and Azure tools, authenticating via Azure
    identity and targeting clusters by subscription/RG/name — so unlike
    kagent-tool-server it is NOT confined to its own cluster
  - an mcp-memory-server for cross-incident recall
  - Kyverno, cert-manager, external-secrets, KRO, ASO

CONSTRAINTS AND HARD-WON FACTS (verified on a live cluster — do not re-litigate)

  1. `kagent-tools` runs with an IN-CLUSTER ServiceAccount and no kubeconfig. Its
     tools ALWAYS query the cluster it is standing in. An agent on cluster A
     cannot use THESE tools to inspect cluster B — it will silently return facts
     about A and nothing will error.
     BUT: this is a property of kagent-tool-server specifically, NOT a law. AKS-MCP
     authenticates via Azure identity and targets clusters by name, so an agent
     given AKS-MCP CAN reach other AKS clusters. A collector script needs only an
     API endpoint and a credential and can run anywhere. Do not over-generalise
     this constraint — we did, and it pushed us toward a per-cluster design that
     may be unnecessary. There is also a TOKEN_PASSTHROUGH env on kagent-tools
     that we did not investigate; if it allows per-request credentials, this
     constraint may dissolve entirely. Worth someone actually checking.
  2. Network direction: the worker→management path is proven (agentgateway
     /a2a/fleet/*, identity at Istio). Whether MANAGEMENT can reach a worker's
     API SERVER is a genuine open question we did not test — for AKS with a public
     API endpoint, or a private endpoint with peering, it likely can. We initially
     stated "management cannot reach workers" as fact; that was over-reading one
     runbook's Istio policy, which governs the A2A path only. Verify before
     designing around it either way.
  3. agentgateway gives routing, rate limiting, timeout and telemetry — NOT
     authentication. The installed CRD has no backend.a2a.authorization.
     Identity is enforced upstream at the Istio AuthorizationPolicy layer.
  4. Kubernetes core/v1 Events frequently have `lastTimestamp: null` and only
     `eventTime` populated, as an RFC3339 MicroTime with fractional seconds.
  5. Event volume is NOT evenly distributed. On our test cluster, 858 of 859
     warning events in a window were Kyverno PolicyViolation from Audit-only
     policies that enforce nothing — and Kyverno emits a duplicate event against
     the ClusterPolicy object for every violation it reports on a real resource,
     so the count is 2x the real violation count.
  6. metrics-server is not guaranteed to be installed. Do not assume
     `kubectl top` works.
  7. `bitnami/kubectl` images no longer pull. Bitnami retired their public catalog.

WHY LGTM DOES NOT ALREADY SOLVE THIS (our belief — challenge it if you disagree)

  Our read is that the managed LGTM setup alerts on single-metric thresholds. It
  fires when one particular thing crosses one particular line. It is weak at:
    - cumulative / composite signals, where no single metric breaches but the
      overall picture has drifted
    - giving an agent a single consumable artifact describing the whole cluster
    - explaining WHY, as opposed to detecting THAT
  There is prior analysis in
  work-agent-bundles/agentic-triage-smoke-tests/LGTM-METRICS-ONLY-COVERAGE.md
  estimating metrics-only alerting at 35-45% useful triage coverage.

  If you think LGTM (or Grafana alerting, or Mimir recording rules, or k8sgpt,
  or Popeye, or Robusta, or Komodor, or something else off the shelf) can do
  this properly, SAY SO — that is a more valuable answer than a bespoke build.
  We would rather lift and shift than maintain something.

QUESTIONS WE WANT YOUR ANSWER TO

  1. What establishes "baseline" and what detects drift from it? Thresholds?
     Rolling statistics? Recording rules? Something learned? Where does that run?
  2. What form does the signal take when it reaches the agent, and how does the
     agent get the supporting evidence without re-querying everything itself?
  3. Where does the investigating agent run, given constraint 1?
  4. How do you avoid alert storms — a cluster-wide problem must produce ONE
     investigation, not N?
  5. How does this behave across a fleet? What crosses the cluster boundary?
  6. How does the agent's report get back to a human, and how do we correct a
     baseline that turns out to be wrong?
  7. What do you deliberately NOT do?

WHAT GOOD LOOKS LIKE

  A design we could build in phases, where phase 1 is useful on its own and does
  not require an LLM. Be explicit about what you are NOT solving. If you think
  the framing above is wrong, say that first — the most useful answer may be
  "you are solving the wrong problem".

DO NOT

  - Assume any cross-cluster tool access exists (see constraint 1)
  - Propose auto-remediation. Remediation is GitOps/HITL-gated here.
  - Propose a new observability stack. We have LGTM and will not run a second one.
```

---SOLUTION BOUNDARY---

## What we actually did — read only after you have your own answer

**Our answer changed once we remembered `aks-certification` exists.** We first
built a standalone system; the current recommendation is to merge a single
`check-baseline` step into that existing workflow instead
(`examples/aks-certification-baseline-patch.yaml`). If your independent answer
also lands on "extend the thing we already have", that is a strong signal. If it
lands somewhere else, we want to hear why.

See `README.md` for the TL;DR and `ARCHITECTURE.md` for the detail. In brief:

- **Baseline:** a Python CronJob every 10 minutes builds one ~4 KB JSON snapshot
  of nine sections, then evaluates it against absolute thresholds plus a rolling
  median over the last 24 snapshots. Runs in-cluster, read-only, stdlib only.
- **Signal:** the detector fires **only on a transition** (healthy→breached, or a
  severity escalation, or a recovery) — never repeatedly while degraded.
- **Evidence handoff:** the workflow reads the immutable snapshot by exact ref and
  pastes the entire JSON **into the agent's prompt** before its first token.
- **Where the agent runs:** on the cluster it is reasoning about, because of
  constraint 1. Cross-cluster carries the *verdict*, not the snapshot.
- **Storm control:** the sentinel never subscribes to raw warning events at all
  (so it cannot double-handle what namespace sensors already own), plus a
  workflow mutex and a durable `incident_key` with a 60-minute correlation window.
- **Reporting:** GitLab issue, gated behind a `REPORT_MODE` ConfigMap that
  defaults to `log-only`.
- **Baseline correction:** not built. Our recommendation is that the agent emits a
  `BASELINE_SUGGESTION` a human merges — never self-applies. A detector that
  widens its own thresholds when it sees noise learns to see nothing, and the
  drift toward "all clear" is undetectable from inside.

### Where we are least confident — attack these

0. **We nearly built a parallel system to one we already owned.** We wrote a
   whole standalone collector before remembering `aks-certification` does most of
   it. That is the single biggest lesson here and it is a process failure, not a
   technical one: we did not inventory what existed before building. If you spot
   us doing it again anywhere else in this design, say so.
1. **Is a bespoke collector right at all?** We chose it over k8sgpt (brings a
   competing LLM loop) and Popeye (scores config hygiene, not live pressure). We
   did not seriously evaluate Robusta, Komodor, or Mimir recording rules. If one
   of those does 80% of this, we would rather use it.
2. **Is 10 minutes the right cadence?** Picked by feel. Too slow for an acute
   incident, possibly too fast for a "brewing" trend.
3. **Are thresholds the right detector?** Ours are hand-picked guesses. A rolling
   median over 24 samples is thin. Nothing here learns.
4. **Is one big JSON blob the right agent interface?** It works and it is cheap,
   but it caps at 200 KB and a 500-node cluster will strain it. Is a queryable
   MCP tool better than a snapshot in the prompt?
5. **Is a per-cluster orchestrator wasteful?** It is N agent deployments for a
   thing that fires rarely. A central agent with per-cluster credentials would be
   one deployment — at the cost of a credential distribution problem. We now
   lean central (AKS-MCP makes it viable, and `aks-certification` is already
   cluster-parameterised), but the trade is real: fleet-wide read credentials in
   one place is a much juicier target than one SA per cluster. Make that call
   deliberately rather than by default.
6. **We ignore the noise instead of fixing it.** We filter Kyverno
   PolicyViolation at source. Arguably the right answer is to fix the Kyverno
   config and delete the Audit-only policies that enforce nothing.

### What we would want you to tell us

Whether the snapshot-plus-transition-detection shape is sound, or whether we have
reinvented something that exists. And whether "the agent runs where its tools
point" is a real constraint or an artifact of how kagent-tools happens to be
configured — if that can be fixed upstream, the whole fleet design changes.
