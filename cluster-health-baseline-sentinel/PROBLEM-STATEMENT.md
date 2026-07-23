# Problem Statement

## What routing does today

`agents/kagent-triage/03-sensor-kagent-triage.yaml` filters on
`body.involvedObject.namespace`, then submits a workflow that resolves a
namespace-specific agent and hands it the event over A2A:

```yaml
filters:
  data:
  - path: body.involvedObject.namespace
    type: string
    value:
    - test-ns
```

The workflow's `find-agent` step falls back to a generic `k8s-agent` when no
namespace-specific agent matches — with no cluster context beyond the single
event that triggered it.

## Where that breaks

The model assumes **the namespace that reported the symptom is the namespace with
the problem**. That assumption fails for every cluster-scope failure:

| Failure | How it presents | What namespace routing does |
|---|---|---|
| Node CPU/memory exhausted | pods pending across many namespaces | N investigations, each seeing "my pod won't schedule" |
| IP exhaustion (CNI subnet) | pod sandbox creation fails cluster-wide | N investigations, none checks the subnet |
| CoreDNS degraded | app-level DNS timeouts everywhere | N investigations of N unrelated apps |
| Node NotReady | evictions across namespaces | N investigations of "my pod died" |
| API server latency | controller lag, stale state | symptoms with no owning namespace at all |
| Restart-rate creep | nothing yet — it is *brewing* | nothing fires at all |

The last row matters most. Namespace routing is **reactive by construction**: it
needs a warning event to exist. Anything that is trending toward failure but has
not failed produces no event, so nothing routes anywhere.

And critically: **we cannot route to a specialist because we do not know the
issue class up front.** That is the whole difficulty. A sensor filter is a
static routing rule; "something is wrong with the cluster generally" has no
static destination.

## Why LGTM does not close it

Our understanding of the managed LGTM setup is that it alerts on metric
thresholds — it fires when one particular series crosses one particular line.
Three consequences:

1. **No composite view.** A cluster can be in trouble with no single metric
   breaching: 85% CPU commit *and* a rising restart rate *and* two degraded
   addons *and* a slow PVC fill. Each is individually under its threshold. The
   overall picture is not.
2. **No consumable artifact.** An agent asked to investigate has to go and query
   everything itself. There is no single "state of the cluster" document.
3. **Detects THAT, not WHY.** Prior analysis in
   `agentic-triage-smoke-tests/LGTM-METRICS-ONLY-COVERAGE.md` estimates
   metrics-only alerting at **35–45%** useful agentic triage coverage, and is
   blunt that metrics are good at detecting unhealthy state and weak at
   explaining it.

This is **not** an argument to replace LGTM. Keep it for time series, history,
and dashboards. The gap is a layer above it.

### The noise problem, measured

On RED, in one 15-minute window:

```
warning events total : 859
  PolicyViolation    : 858   ← Kyverno, Audit-only, enforces nothing
  everything else    :   1
```

Worse, Kyverno emits a **duplicate event against the ClusterPolicy object for
every violation it reports on a real resource** — measured at exactly 50.0% of
1192 events. So 258 genuinely violating objects generated 1192 events, arriving
in bursts of 778 in a single minute.

Any threshold over raw event volume in that environment is meaningless. This is
the concrete reason "just alert on event rate" does not work, and why exclusion
at source is a first-class design requirement rather than a tuning detail.

## What we actually want

> Some process that periodically establishes whether a cluster is within its
> normal baseline. If it drifts, that signal reaches an agent. The agent uses
> every tool it has — Kubernetes, network, AKS-MCP, GitLab, the KB, other agents
> — to work out what is going on, whether it has happened before, and what to do
> about it. It comes back with a report. If the report says the baseline was
> wrong, we correct the baseline.

Two properties fall out of that statement:

- **Generic, not routed.** One destination for "we don't know what this is",
  which then delegates once it does.
- **Evidence-first.** The agent should not have to re-derive the state that
  triggered it. Hand it the snapshot.

## Explicit non-goals

- Not replacing per-namespace sensors. They keep the known-shape fast path.
- Not replacing LGTM.
- Not auto-remediating. Diagnosis plus a HITL packet; remediation stays
  GitOps/workflow-gated.
- Not a new observability stack.
