# Cluster Health Baseline Sentinel — TL;DR

**One-line ask:** catch cluster-scope problems that namespace-routed triage
structurally cannot, by adding **baseline drift detection to the certification
workflow we already have**, and handing the resulting report to an agent that
investigates with all its tools.

Built and proven on the RED homelab cluster, 2026-07-15. Not proven at work.

> ## ⚠️ Direction changed — read this first
>
> This bundle was built as a **standalone** sentinel (own collector, own sensor,
> own workflow). It works, and it is proven end-to-end. But the repo already has
> **`aks-certification`** — deployed on RED for 169 days — which runs real health
> checks (api-server, dns, networking, storage, critical-pods, node-health, rbac,
> secrets) and emits one structured JSON report. That is ~70% of the same job,
> including four checks the standalone version never had.
>
> **The recommendation is now: merge, don't build alongside.** Add one
> `check-baseline` step to the existing DAG. See
> `examples/aks-certification-baseline-patch.yaml`.
>
> What certification cannot do is **drift** — every check is pass/fail on current
> state, so a Ready node passes at 93.6% CPU commit with no headroom. It would
> certify RED healthy today. That gap is the only thing the baseline adds, and
> it is the whole reason this exists.
>
> The standalone manifests in `agents/cluster-health-sentinel/` remain valid and
> proven — treat them as the reference implementation of the pieces being merged,
> not as the thing to deploy.

---

## The problem in three sentences

Today's sensors filter Kubernetes warning events by `involvedObject.namespace`
and route to the agent that owns that namespace. That works when the failing
namespace *is* the problem, and fails completely when node pressure, IP
exhaustion, or a degraded addon shows up as symptoms in ten namespaces at once —
each namespace agent investigates its own slice and none sees the shared cause.
LGTM does not fill the gap: it alerts on single-metric thresholds, so it fires on
*one particular thing*, not on cumulative drift across many weak signals.

## What we built

```
CronJob (10 min)  →  snapshot ConfigMap  →  baseline detector
                          (immutable)            │
                                                 │ ONLY on transition
                                                 ▼
                                  Sensor → Workflow → Agent → GitLab issue
                                              │         │
                        reads snapshot by ref ┘         └ snapshot inlined in prompt
```

Four ideas carry the whole design:

1. **One JSON document.** Nine sections (nodes, scheduling, addons, events,
   workload stress, storage, control plane, IP capacity, triage storm) in one
   ~4 KB artifact a human can read with one `kubectl get cm` — and an LLM can
   consume in one shot. Phase 1 ships this alone and is useful with no agent at all.
2. **The agent is handed the evidence.** The snapshot is pasted *into the prompt*
   before the agent's first token. It opens with the data and spends its tool
   budget only on what the snapshot lacks.
3. **Fire on transition, never on state.** Healthy→breached fires once.
   Breached→breached is silent. A degraded cluster does not re-alert every 10 minutes.
4. **Exclude noise at source.** On RED, 858 of 859 warning events were Kyverno
   `PolicyViolation`. Filtering them took the signal from 1078 to 2.

## Proven on RED

| | |
|---|---|
| Chain | collector → breach → webhook `HTTP 200` → sensor → workflow → agent → GitLab issue #444 |
| Snapshot | 3.9 KB, ~4 s, 9 sections, 8 OK / 1 unavailable |
| Real breach caught | `node_cpu_commit` — 93.6% of allocatable on the only node |
| Agent verdict | `ROOT_LAYER: node-pressure`, blast radius scoped, correctly declined to delegate |
| Phase 3 gate | Agent CRD `Accepted=True` / `Ready=True` — Agent-type tool refs work |

The verdict quality is the part worth reading. The snapshot reports *cumulative*
restart counts (kindnet 75, metallb 62) which look alarming and mean nothing
without a delta. Unprompted, the agent checked with its own tools, found they were
~47 days old, and discounted them as chronic. It also read `ip_capacity:
unavailable` as *"no data, not evidence of health or exhaustion"*.

## The one architectural constraint that decides the fleet design

`kagent-tools` runs with an **in-cluster ServiceAccount and no kubeconfig**. Its
tools always query the cluster it is standing in. So a management-cluster
orchestrator reasoning about a worker's snapshot would call `k8s_get_resources`
and silently drill into **the management cluster** — every tool-sourced fact about
the wrong machine, and nothing errors.

**Therefore: the orchestrator runs where its tools point.** One per worker
cluster. What crosses the boundary is the *verdict* (~2 KB of reasoned text), not
the snapshot (up to 200 KB of raw JSON). This also matches the existing direction
of travel — workers egress to management, management cannot reach in — so any
design where a fleet agent *pulls* a worker's snapshot is dead on arrival.

## Six defects, and how each was found

None were caught by design review or by 44 passing offline unit tests. That is the
headline lesson, not a footnote.

| Defect | Found by |
|---|---|
| RCE — trigger payload interpolated into Python source; `"""` breaks out and executes with `argo-events-sa` creds | testing a hunch while drawing a diagram |
| Every time window was a no-op — `_parse_ts` rejected `eventTime` MicroTime, returned `None`, and `if ts and ts < cutoff` let `None` through, counting all retained history | checking a subagent's number that disagreed with mine — it was right |
| PolicyViolation never excluded, though a comment claimed it was; spike check needed 2577 events to fire | first real snapshot |
| `node_cpu_commit` never checked — the exact "brewing" case, collected and ignored | reading the first snapshot by eye |
| Silent cap — nodes truncated to 20 *before* detection, so node 21+ never checked | writing the fix for the above |
| `bitnami/kubectl` is dead repo-wide (23 other YAML manifests still reference it) | ImagePullBackOff on the first real run |

The tests passed because they asserted our assumptions back to us: synthetic
events carried the timestamp format we imagined, not the one Kubernetes emits.

## Files

| File | What |
|---|---|
| `TEAMS-MESSAGE.md` | Paste-ready message to socialise the idea |
| `FRONT-SHEET.md` | One-page summary for a work-side reader |
| `REVERSE-PROMPT.md` | **The brief for a team solving this independently** — problem, constraints, no solution |
| `PROBLEM-STATEMENT.md` | Why namespace routing and LGTM both miss this |
| `ARCHITECTURE.md` | The flow, where each piece runs, single- vs multi-cluster |
| `LESSONS.md` | The seven defects in full, and what they imply for the work rollout |
| `LIFT-AND-SHIFT.md` | What to change to run this at work |
| `prompts/orchestrator-system-message.md` | The agent's system message + output contract |
| `evidence/` | Real snapshot, real agent verdict, real GitLab issue body |
| `examples/aks-certification-baseline-patch.yaml` | **The recommended path** — the one step to bolt onto `aks-certification` |
| `examples/cronworkflow-certification.yaml` | The schedule that turns a provisioning gate into a health monitor |
| `examples/MANIFESTS.md` | Index of the standalone manifests + key snippets |

## The merge, concretely

`collect.py` gained a `MODE=check` that emits the certification contract instead
of dispatching its own webhook:

```json
{"check": "baseline", "status": "failed",
 "verdict": "warning", "previous_verdict": "healthy", "transitioned": true,
 "details": [{"check": "node_cpu_commit", "severity": "warning",
              "detail": "node X CPU requests at 93.6% of allocatable"}]}
```

Three edits to `aks-certification`: add the task to the DAG, add one parameter to
`generate-report`, add an `escalate-to-agent` step. The escalation rule:

> **any check failed, OR the baseline moved → call the agent.**

Two things had to survive the merge, and both were earned the hard way:

1. **Fire-once state.** A workflow is stateless between runs, so nothing in the
   report says whether DNS was already broken last time. Without state, a
   scheduled run becomes a pager loop. The escalate step tracks the *set* of
   failing checks in a ConfigMap and fires when that set **changes** — same
   "fire on change, not on state" rule the baseline uses for its verdict.
2. **Untrusted-payload handling.** The report goes to the agent via an env var,
   never interpolated into a script body. We shipped that RCE once already
   (`LESSONS.md` §1).

Implementation lives at `agents/cluster-health-sentinel/` in this repo.
Design history and review findings: `WORK-CLUSTER-HEALTH-SENTINEL-PLAN.md`.

## Status — read before deploying anything

**Deployed to RED, then stood down.** The CronJob is **suspended**, the sensor and
EventSource are **deleted**. The orchestrator Agent is left deployed but idle
(zero tokens when not called). Two snapshot ConfigMaps retained as evidence.

Report mode is `log-only` — the safe default. It created exactly one GitLab issue
to prove the path, then was reverted.

**Not proven:** multi-node clusters (RED is single-node kind), the Alertmanager
route, the storm detector, all four fault-injection cases, and every cross-cluster
path. Baselines are educated guesses, not tuned numbers — that is what observe
mode is for.
