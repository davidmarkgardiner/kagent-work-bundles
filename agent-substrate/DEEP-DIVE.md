# Agent Substrate — Deep Dive

How the actor runtime works, what each component does, and what actually happens on a
request. Read [`README.md`](README.md) first for the why.

---

## 1. The core idea: actors, not pods

A normal kagent agent is a Kubernetes **Deployment** — one (or more) pod that is scheduled,
booted, and then sits resident forever, holding RAM and a CPU share even while doing
nothing. Agent workloads are *mostly nothing*: they block on humans, tool calls, and LLM
round-trips.

Substrate replaces the 1-agent-1-pod model with an **actor model**:

- An **actor** is one agent instance. It has RAM state and a filesystem, but no dedicated pod.
- A **worker** is a real pod that hosts many actors, one at a time, restoring/suspending them.
- When an actor is idle it is **snapshotted** to object storage and evicted from the worker —
  freeing RAM. The worker is now free to host another actor.
- When a request arrives the actor is **restored** from its snapshot into a worker in ~ms and
  serves the request, then re-snapshots.

Because actors spend ~all their time suspended, a single worker pod can back-stop **many**
actors (the upstream demo shows ~30x). This is classic oversubscription, made safe by
snapshot/restore + gVisor isolation.

## 2. Components

Installed into the `ate-system` namespace by the substrate Helm charts:

| Component | Kind | Role |
|---|---|---|
| **ate-api-server** | Deployment | Control plane. gRPC endpoints for actor/worker lifecycle. kagent's controller talks to this (`ateApiEndpoint=dns:///api.ate-system.svc:443`). |
| **atecontroller** | Deployment | Reconciles `WorkerPool` and `ActorTemplate` CRs into running workers. |
| **atelet** | DaemonSet | Node agent. Coordinates snapshotting and state transfer on each node. |
| **atenet** (dns / router) | Deployment(s) | Networking layer: DNS-based discovery, Envoy routing, proxy sidecars between actors/workers. |
| **ateom-gvisor** | interior-pod helper | Runs *inside* a worker/actor pod. Issues the gVisor checkpoint/restore commands. This is where the gVisor userspace lives. |
| **podcertcontroller** | Deployment | Pod Certificate signer — mTLS identity for actors/workers. |
| **valkey-cluster-{0..5}** | StatefulSet | In-memory coordination / metadata store (6 shards). |
| **rustfs** | Deployment | S3-compatible object store holding actor **snapshots** (golden + per-session). |
| **kubectl-ate** | CLI | `kubectl ate ...` for managing atespaces/actors directly. |

kagent adds one CRD on its side: **`SandboxAgent`** (`kagent.dev/v1alpha2`), plus a
substrate-aware controller (enabled with `controller.substrate.enabled=true`) and an
optional **substrate worker pool** (`substrateWorkerPool.create=true`).

## 3. Request lifecycle (what happens when you ask the agent something)

```
                    ┌─────────────────────────────────────────────┐
                    │            ate-api-server (control)          │
                    └───────────────▲─────────────┬───────────────┘
 kagent controller ─ reconciles ────┘             │ schedule actor
 SandboxAgent → ActorTemplate                     ▼
                                    ┌──────────────────────────────┐
   request ──► atenet (Envoy/DNS) ─►│  worker pod (hosts actors)   │
                                    │   ┌────────────────────────┐ │
                                    │   │ ateom-gvisor: RESTORE  │ │◄── snapshot from rustfs
                                    │   │  gVisor actor runs the │ │
                                    │   │  Go ADK agent + LLM    │ │──► LLM (model endpoint)
                                    │   │ ateom-gvisor: SNAPSHOT │ │──► snapshot to rustfs
                                    │   └────────────────────────┘ │
                                    └──────────────────────────────┘
                                                  │
                                       actor → Suspended (0 RAM/CPU)
```

1. **Reconcile.** You `kubectl apply` a `SandboxAgent`. kagent's substrate controller
   registers it with `ate-api-server` as an `ActorTemplate` bound to a `WorkerPool`. A
   **golden snapshot** of the freshly-booted Go ADK agent is captured.
2. **Idle.** No traffic → the actor is `Suspended`. Its snapshot lives in rustfs; it holds
   **no worker RAM**.
3. **Request.** A query hits `atenet`, which routes to a worker. `ateom-gvisor` **restores**
   the actor from its snapshot (golden, or the last per-session snapshot) into a gVisor
   sandbox in ~ms.
4. **Execute.** The Go ADK agent runs inside gVisor, makes the LLM call to your
   `ModelConfig` endpoint, produces a response.
5. **Re-snapshot + suspend.** `ateom-gvisor` snapshots the actor's RAM **and** filesystem
   back to rustfs and evicts it. The actor is `Suspended` again; the worker is free.

State — both memory and disk — survives the suspend. That is the property plain Deployments
can't give you without external state plumbing.

## 4. Why gVisor (and why it's the porting constraint)

gVisor (`runsc`) is a **user-space kernel**. It intercepts the actor's syscalls in userspace
instead of passing them to the host kernel, giving:

- **Isolation** strong enough to run untrusted code / tools (the sandbox demos run Alpine
  and Claude Code inside actors).
- **Checkpoint/restore** of a whole process tree (RAM + fds + fs) — the mechanism behind
  suspend/resume.

Substrate bundles gVisor userspace in the `ateom-gvisor` image (gVisor-in-pod), so it does
**not** require a node-level gVisor `RuntimeClass`. But checkpoint/restore still needs:

- **privileged / elevated capabilities** in the actor pod, and
- a **host kernel** that supports the syscalls gVisor's C/R relies on.

This is why GKE (which offers GKE Sandbox = managed gVisor) is a first-class target, and why
locked-down clusters with admission policy (Kyverno/Gatekeeper blocking privileged pods) are
the hard case. See [`WORK-CLUSTER-ADAPTATION.md`](WORK-CLUSTER-ADAPTATION.md).

## 5. Constraints & sharp edges

- **Go ADK runtime only.** Python declarative agents don't run on substrate yet — a real
  limitation given most existing kagent agents on our clusters are `runtime: python`.
- **Early-stage (v0.0.x).** Unstable APIs, no backward-compat, not production-ready.
- **Heavier baseline.** 6x valkey + object store + control plane is a non-trivial standing
  cost — it only pays off when you host *many* idle actors above it.
- **Model reachability.** The actor makes the LLM call from inside the cluster; the
  `ModelConfig` endpoint must be reachable from there (in-cluster gateway or internet).
- **Snapshot storage.** rustfs holds every snapshot; storage grows with actor count and
  session history — plan capacity + GC.

## 6. Mental model in one line

> Substrate is to agents what serverless function cold-start-from-snapshot (Firecracker-style)
> is to functions — but built on gVisor checkpoint/restore, wired into kagent via the
> `SandboxAgent` CRD, so an idle agent costs ~nothing and resumes with full state.
