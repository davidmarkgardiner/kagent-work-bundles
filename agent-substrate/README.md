# Agent Substrate on kagent — Work Bundle

Run declarative kagent agents as **suspend/resume gVisor actors** instead of always-on
Deployments. Idle agents snapshot to storage and free their RAM; a request re-animates
them from a golden snapshot in milliseconds. The upstream demo shows ~**30x** actor-to-pod
multiplexing.

This bundle is a reproducible package to stand it up, prove it works, and adapt it to a
work cluster. **It has been run live, twice:**
- On a real, already-running kagent cluster (`red`) — substrate added as 4 charts, then a
  `SandboxAgent` driven **purely by `kubectl apply`**, no patches. This is the work-shaped
  path: [`evidence/RUN-RED-2026-07-16.md`](evidence/RUN-RED-2026-07-16.md).
- On an isolated kind cluster (first proof + the golang-adk registry workaround):
  [`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md).

Both captured the full actor lifecycle: boot → gVisor checkpoint → suspend-to-object-store.

- Upstream docs: https://kagent.dev/docs/kagent/examples/agent-substrate
- Upstream repo: https://github.com/agent-substrate/substrate
- Deep architecture write-up: [`DEEP-DIVE.md`](DEEP-DIVE.md)
- **Where it fits (orchestration vs execution):** [`ARCHITECTURE-FIT.md`](ARCHITECTURE-FIT.md)
- Adapting to the work cluster (AKS): [`WORK-CLUSTER-ADAPTATION.md`](WORK-CLUSTER-ADAPTATION.md)
- **Air-gapped AKS install and verification:** [`AIRGAPPED-AKS-README.md`](AIRGAPPED-AKS-README.md)
- **Copy-ready GitLab issue:** [`GITLAB-ISSUE-AIRGAPPED-AKS-EVALUATION.md`](GITLAB-ISSUE-AIRGAPPED-AKS-EVALUATION.md)

> **Known issue (registry):** the Go ADK agent-runtime image resolves against the chart's
> global `registry` value. If that is the default `cr.kagent.dev` mirror (as on a stock
> kagent 0.9.9), it 404s (`NAME_UNKNOWN`) and actors never boot. **Fix at source: set
> `registry: ghcr.io`** — proven on the `red` run, where no patch was needed at all. The
> kind install script auto-repoints the per-actor image as a fallback. This is **separate**
> from `substrateWorkerPool.ateomImage` (the worker host), which is its own helm value.
> Details in [`evidence/RUN-2026-07-16.md`](evidence/RUN-2026-07-16.md).

---

## What it is

Agent Substrate ("ATE") is an actor runtime that sits **on top of** a normal Kubernetes
cluster without taking it over. It multiplexes many agent "actors" onto a small pool of
"worker" pods, exploiting the fact that agent workloads are idle almost all the time
(waiting on a human, a tool call, or an LLM).

kagent integrates with it through a new CRD, **`SandboxAgent`**. Instead of a per-agent
Deployment, a `SandboxAgent` runs as a substrate actor: it restores from a snapshot to
serve a request, then re-snapshots and goes `Suspended` — using **zero CPU and zero RAM
between requests** while keeping its in-memory + filesystem state.

```
Classic kagent                    Substrate kagent
--------------                    ----------------
1 Agent  = 1 Deployment (always   N SandboxAgents = M worker pods (N >> M)
           on, always eating RAM)  actors suspend to snapshot when idle,
                                    restore on demand in ~ms
```

## Why it matters (benefits)

| Benefit | Classic Deployment agent | SandboxAgent (substrate) |
|---|---|---|
| **Idle cost** | Full pod RAM/CPU reserved 24/7 | ~0 between requests (suspended) |
| **Density** | 1 agent ≈ 1 pod | ~30 actors per worker pod (upstream demo) |
| **Cold start** | New pod schedule + image pull + boot | Restore from golden snapshot (~ms) |
| **State across idle** | Lost unless externalised | RAM **and** filesystem preserved via snapshot |
| **Isolation** | Container (shared kernel) | gVisor sandbox (user-space kernel) |
| **Blast radius** | Namespace RBAC | gVisor + per-actor network policy |

Net: you can host a **large fleet of rarely-active agents** (per-team, per-tenant,
per-customer, on-call helpers) for a fraction of the standing footprint, with stronger
isolation than plain containers.

## Use cases

- **Long-tail agent fleets** — hundreds of per-team / per-repo / per-tenant agents that are
  each used minutes a day. Pay for the minutes, not the days.
- **Sandboxed tool + code execution** — gVisor makes it safe to let an agent run shell,
  build code, or exec untrusted tools (Claude Code / Codex / MCP tool servers) with a
  user-space kernel boundary.
- **Stateful sessions that idle** — an agent mid-conversation or mid-task keeps its RAM and
  scratch filesystem while suspended, then resumes exactly where it left off. No re-hydration
  glue.
- **Bursty / spiky triage** — incident, chaos, and alert-triage agents that sit idle then
  all wake at once; the worker pool absorbs the burst without N idle pods.
- **Cost-capped experimentation** — spin up many candidate agents for A/B or eval work
  without provisioning a pod per candidate.

## Requirements

- kagent **>= 0.9.7** (substrate controller integration). This bundle uses **0.9.9**.
- Agent Substrate charts **0.0.6** (`ghcr.io/kagent-dev/substrate/helm/*`).
- A Kubernetes cluster — kind is the documented happy path. Data plane ships 6x valkey +
  an object store (rustfs) + worker pool; budget **~8Gi RAM**.
- An OpenAI-compatible model endpoint reachable **from inside the cluster**. On a fresh /
  isolated cluster with no in-cluster AI gateway, use an internet endpoint (OpenRouter,
  OpenAI). See [`examples/modelconfig-openrouter.yaml`](examples/modelconfig-openrouter.yaml).
- **Go ADK runtime only.** Python declarative agents are **not** supported on substrate yet.

> ⚠️ Substrate is early-stage (v0.0.x) — unstable APIs, no backward-compat guarantees, not
> production-ready. Treat this as an evaluation / platform-readiness exercise.

## Quickstart

```bash
# key is read from stdin — never in args or history
printf '%s\n' "$OPENROUTER_API_KEY" | bash scripts/install-substrate.sh
```

That script (idempotent) does the full walkthrough on an isolated `kagent-substrate` kind
cluster: substrate CRDs + control/data plane → kagent + substrate flags → an
internet-reachable `default-model-config` → the `hello-substrate` SandboxAgent → waits for
`Ready` and dumps final state. Override `CLUSTER`, `SUB_VER`, `KAGENT_VER`, `MODEL_*` via env.
It sets `registry=ghcr.io`, the declarative runtime-image fix proven on the live run; it does
not patch a generated `ActorTemplate` or stop the controller. The input key is passed to Helm
from a temporary mode-0600 file rather than a process argument. This remains a
kind-only demo path: Helm release state can retain configured values, so never use a work key.

### Verify

```bash
kubectl get pods -n ate-system                       # control + data plane Running
kubectl get sandboxagents -n kagent -o wide          # hello-substrate Ready
kubectl port-forward -n kagent svc/kagent-ui 8001:80 # then open http://localhost:8001
```

Ask the agent *"What are you, and where are you running?"* — it answers that it is a Go ADK
declarative agent running inside a gVisor actor. Behind the scenes a per-session gVisor
actor restores from snapshot, makes the LLM call, re-snapshots, and returns to `Suspended`.

For an existing AKS cluster, use the air-gapped AKS guide and its read-only
operational verifier instead of this kind-only installer:

```bash
bash scripts/verify-aks-substrate.sh \
  --context {{KUBE_CONTEXT}} \
  --sandboxagent hello-substrate
```

## What's in this bundle

| Path | Purpose |
|---|---|
| `README.md` | This file — overview, benefits, use cases, quickstart |
| `DEEP-DIVE.md` | Architecture: control/data plane, actor lifecycle, snapshot/restore, gVisor |
| `ARCHITECTURE-FIT.md` | Orchestration vs execution; mapping to the triage pipeline; when it's worth it |
| `WORK-CLUSTER-ADAPTATION.md` | How to run this on the work cluster (AKS), gVisor/Kyverno gate, checklist |
| `AIRGAPPED-AKS-README.md` | Pinned artifact, Flux/Helm order and air-gapped AKS verification guidance |
| `GITLAB-ISSUE-AIRGAPPED-AKS-EVALUATION.md` | Copy-ready Kanban issue for the air-gapped AKS evaluation |
| `scripts/install-substrate.sh` | One-shot, idempotent, stdin-key installer |
| `scripts/verify-aks-substrate.sh` | Read-only AKS CRD, rollout, WorkerPool and SandboxAgent verifier |
| `scripts/teardown.sh` | Delete the kind cluster and reclaim resources |
| `examples/sandboxagent-hello.yaml` | The demo `SandboxAgent` CRD |
| `examples/modelconfig-openrouter.yaml` | Internet-reachable model endpoint for fresh clusters |
| `evidence/` | Captured proof from a real run (pod lists, CRD status, actor lifecycle) |
| `WORD-HANDOVER-SUMMARY.md` | Concise, paste-ready decision and implementation summary |
