# Where Agent Substrate Fits (and Where It Doesn't)

The single most important framing to get right before pitching this internally.

---

## Substrate is an execution runtime, not a workflow engine

> **Substrate is Kubernetes-for-agent-execution, not a framework for building or orchestrating
> agents.**

It makes each agent step **cheap to execute** (suspend/resume gVisor actors). It does **not**
decide *which* agent runs next, handle retries, approvals, branching, or state across a
multi-step process. That is a **workflow engine's** job.

| Layer | Responsibility | Examples |
|---|---|---|
| **Workflow / orchestration** | what runs next, retries, approvals, branching, state | Argo Workflows, Temporal, Dapr Workflows, **kagent** (A2A/graph) |
| **Execution runtime** | run each agent task efficiently, low latency, high density | **Agent Substrate** |
| **Tools** | expose systems as callable tools | MCP servers (k8s, Grafana, GitHub, Azure, Terraform) |
| **Reasoning** | the actual LLM inference | Azure OpenAI / Claude / Gemini |

Keeping these independent is what makes the platform scale, swap, and evolve cleanly.

## Mapping to the current triage architecture

Today:

```
Alertmanager → Kafka → Triage Agent → Grafana MCP → Kubernetes MCP → Azure OpenAI
```

With substrate the **logic is unchanged** — only the execution layer changes:

```
Alertmanager → Kafka → [Orchestrator: kagent/Argo] → Substrate warm actor pool
                                                          → MCP servers → Azure OpenAI
```

The triage agent(s) become **SandboxAgents** that suspend when idle and restore per alert. For
bursty alert storms, the worker pool absorbs the burst without N always-on triage pods.

## When substrate earns its keep

- **Hundreds/thousands of short-lived agent tasks** — bursty alert/chaos/incident triage.
- **Many concurrent workflows** each spawning agent steps.
- **GPU-backed local inference** — one GPU worker serves many suspended agents instead of
  churning pods.
- **High pod churn today** — you're paying scheduling + cold-start cost per agent invocation.

## When it's overkill

- One assistant, one long-running coding agent, or a handful of background workers → plain
  Kubernetes Deployments are simpler. The 6x-valkey + object-store baseline only pays off above
  a large idle-actor fleet.

## The three honest blockers for us *right now*

1. **Go ADK runtime only.** Substrate runs `runtime: go` agents. Our existing fleet on `red`
   is almost entirely `runtime: python`. Migrating triage/remediation agents to Go ADK is real
   work — or we wait for Python-on-substrate support.
2. **Pre-production (v0.0.x).** Unstable APIs, no backward-compat, plus the golang-adk registry
   bug we hit (see [`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md)). Fine for a
   platform-readiness track; not yet for prod triage.
3. **No A2A REST invocation for sandbox agents (kagent 0.9.10).** Verified on `red`:
   deployment-mode agents answer via `POST /api/a2a/{ns}/{name}`; substrate agents 404 there.
   So the triage pipeline above **cannot call a substrate agent over the standard A2A HTTP
   path today** — it would drive deployment agents, or invoke the actor via the data plane.
   See [`evidence/RUN-RED-2026-07-16.md`](evidence/RUN-RED-2026-07-16.md).

## Recommendation

Treat substrate as a **platform-readiness / cost-efficiency track**, not a migration:

1. Keep orchestration where it is (kagent / Argo). Do **not** try to make substrate orchestrate.
2. Pick **one** high-churn, bursty, low-duty-cycle agent (e.g. alert triage) as the pilot.
3. Port just that agent to Go ADK, run it as a `SandboxAgent` on a dedicated node pool.
4. Measure the actual win: idle RAM reclaimed, cold-start latency, density vs the Deployment
   baseline. Decide from numbers, not the pitch.
