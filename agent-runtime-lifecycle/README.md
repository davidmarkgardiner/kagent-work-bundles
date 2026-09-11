# Kagent chat, pod, actor, and harness lifecycles

## TLDR

The API and UI do not decide how many pods run. The selected kagent resource
and its runtime decide that.

| Model | What starts for a request or chat? | What happens after an answer? |
| --- | --- | --- |
| Normal kagent `Agent` | Nothing new. The request uses an existing Deployment pod. | The pod stays running. Session IDs keep chat histories separate inside the shared service. |
| Argo calls a normal `Agent` | Argo runs its caller pod or Workflow Agent. The target agent already exists. | The Argo pod follows Workflow cleanup policy. The target agent and MCP pods stay running. |
| Kubernetes Job per request | Kubernetes creates a Job pod. | The process exits. A Job TTL or another controller must delete the Job and pod. |
| Substrate `SandboxAgent` | kagent creates or resumes one logical actor for that session on a warm worker pod. | kagent snapshots and suspends the actor after the response body closes. The worker is wiped and reused. The actor remains until session cleanup. Snapshot bytes follow a separate retention policy. |
| Substrate `AgentHarness` | The current implementation resumes one actor for the harness. Its ACP process holds multiple chat sessions. | Closing the UI connection leaves the actor running. An explicit suspend snapshots it and frees the worker. |

Substrate does not normally create and delete one Kubernetes pod per prompt.
It restores an isolated actor into an existing worker pod, runs the request,
then removes that actor from the worker. For a `SandboxAgent`, each independent
chat or Argo incident must use a unique `contextId`. Reusing a `contextId`
intentionally reuses the same actor and conversation state.

The active environment is disposable. Its saved state is not. Suspending an
actor preserves its memory and disk snapshot. Deleting the kagent session
deletes the actor record, but snapshot data follows the Substrate storage and
garbage-collection policy.

Read the rest of this page for the exact API, UI, isolation, and cleanup
lifecycles.

## Scope

This page explains what starts when a user opens a chat or sends a request to
kagent. It compares four execution models and the Argo caller lifecycle:

- a normal kagent `Agent` backed by a Kubernetes `Deployment`;
- a Kubernetes `Job` created for each request;
- a kagent `SandboxAgent` backed by Agent Substrate; and
- an OpenClaw or Hermes `AgentHarness`, which also runs on Agent Substrate.

The UI, API, A2A, and ACP are request and control protocols. The Kubernetes
resource type and configured runtime control the compute lifecycle. An Argo
Workflow is a caller unless its templates run the agent process themselves.

## Keep the resource lifecycles separate

Five objects can exist at the same time, but they have different owners and
lifetimes.

| Object | Owner | Typical lifetime |
| --- | --- | --- |
| Chat session | kagent and its session store | Until the user deletes it or retention removes it |
| Normal agent pod | Kubernetes `Deployment` | While the `Agent` requests one or more replicas |
| Substrate worker pod | `WorkerPool` | While the platform provides worker capacity |
| Substrate actor | kagent and the Substrate control plane | From first use until session or agent cleanup |
| MCP server pod | Its own `Deployment`, `MCPServer`, or external owner | Independent of an agent chat |

Stopping a chat does not imply that Kubernetes stops an agent pod. Suspending
an actor does not imply that Kubernetes deletes a worker pod. Suspending an
agent also does not stop a separate PostgreSQL MCP server.

## How chats remain separate

A normal `Agent` uses logical session isolation. The A2A `contextId` becomes
the kagent session ID. kagent loads events by the user ID and session ID before
each request. Separate IDs therefore produce separate model histories even
when the requests enter the same Deployment pod.

Logical isolation is not a separate security boundary. Sessions in one agent
pod share the process, filesystem, service account, credentials, CPU, and
memory. A bad custom tool can leak state through a global variable, a shared
temporary filename, or an unkeyed cache. A crash, memory leak, or stuck request
can also affect every chat on that replica.

A Substrate `SandboxAgent` adds an execution boundary. Each session ID maps to
one actor with its own sandboxed process, memory, and disk state. Sessions can
use the same worker pod at different times, but Substrate wipes the worker
before reassigning it. This design reduces cross-session process and filesystem
risk. It does not isolate shared databases, MCP servers, model quotas, or
credentials unless those systems also enforce a separate identity or policy.

Use these controls in either model:

- Generate an unguessable `contextId` for every independent chat or incident.
- Bind the session to the authenticated user or tenant.
- Reuse a `contextId` only when the caller wants conversation continuity.
- Give the agent and its MCP tools the least privilege they need.
- Keep custom tools stateless, or key their state by both the user and session.
- Set request, concurrency, timeout, token, CPU, and memory limits.
- Record the `contextId`, Argo Workflow UID, agent name, and tool calls in traces.
- Test two concurrent sessions with unique sentinel values and check responses,
  tool calls, files, and logs for cross-session data.

Use separate agents, identities, namespaces, or WorkerPools when tenants do not
trust each other. A per-session actor limits the execution failure domain, but
an overprivileged shared database credential keeps a shared data failure
domain.

## Normal kagent Agent

### Creation and request path

```text
GitOps applies Agent
        |
        v
kagent controller creates Deployment and Service
        |
        v
ReplicaSet creates agent pod before any chat
        |
        v
UI or A2A request -> Service -> existing agent pod
```

The `Agent` is desired state. The kagent controller translates that resource
into a Kubernetes `Deployment` and supporting objects. The Deployment defaults
to one replica unless its configuration says otherwise.

The pod starts during reconciliation, not when the first prompt arrives. The
same pod can serve many requests and chat sessions. If there are several
replicas, a Service can route requests among them, subject to the runtime's
session and storage design.

### What happens when the UI chat closes

Closing the tab, navigating away, or closing the chat WebSocket does not change
the Deployment's desired replica count. The pod stays `Running` and ready for
another request.

The pod restarts or gets replaced only when another lifecycle event occurs.
Examples include:

- the process crashes;
- a readiness or liveness policy causes replacement;
- a node fails or evicts the pod;
- the Deployment rolls out a new image or configuration;
- an operator or autoscaler changes the replica count; or
- GitOps removes the `Agent` or its Deployment.

Deleting a Deployment-managed pod by hand does not stop the agent. The
ReplicaSet creates a replacement because the desired replica count has not
changed.

### Benefits

- The agent is already running when a request arrives.
- Kubernetes Deployments, Services, probes, rollouts, and logs are familiar.
- The runtime has no snapshot, restore, or shared-worker dependency.
- A small number of busy agents can use reserved capacity predictably.

### Costs and limits

- Each agent keeps at least one pod resident while idle.
- A large fleet creates many pods, Services, and standing memory reservations.
- In-process state does not survive pod replacement unless the runtime stores
  it outside the process or on durable storage.
- A standard container shares the node kernel unless the platform adds a
  stronger sandbox runtime.

## Kubernetes Job for each request

This is the model that most closely matches "start a pod, run once, and clean
it up." It is not the default kagent `Agent` model.

```text
API or workflow creates Job
        |
        v
Job controller creates pod
        |
        v
container performs one bounded task and exits
        |
        v
pod becomes Succeeded or Failed
        |
        v
TTL controller deletes Job and pod after the configured delay
```

The container stopping does not delete the Kubernetes objects immediately.
Without `ttlSecondsAfterFinished`, completed Jobs and pods normally remain so
operators can inspect their status and logs.

### Benefits

- Each task gets a separate pod and resource limit.
- Completion, retry, deadline, and failure status are explicit.
- There is no standing agent pod between tasks.
- Jobs fit bounded, non-interactive work such as reports, exports, and tests.

### Costs and limits

- Scheduling, image pulls, container startup, and sidecar startup add latency.
- High request volume creates pod churn and Kubernetes API load.
- A new pod has no previous in-memory state.
- Interactive or multi-turn chat needs an external session store and a routing
  layer.
- A burst can wait for nodes to scale before Kubernetes can schedule its pods.

## Argo Workflow that calls an agent API

An Argo Workflow can call an existing agent without running that agent inside
the Workflow pod.

### Container or script template

If a container or script template uses `curl` or a client library to call the
agent, Argo creates a Workflow pod for that template node. The caller exits
after it receives the response, so its pod reaches `Succeeded` or `Failed`.

```text
Argo creates caller pod
        |
        v
caller sends API request -> existing kagent Service -> existing agent pod
        |                                               |
        |<--------------- analysis response ------------|
        v
caller exits and its pod completes
        |
        v
Argo deletes the completed pod only if podGC says to do so
```

The target agent pod does not complete merely because it returned an answer.
Its Deployment still requests a running replica. The MCP server pod is also a
separate workload and remains running.

### HTTP template

Argo `http` and plugin templates use a Workflow-scoped Argo Agent pod. A
Workflow that contains several HTTP template nodes does not necessarily create
one caller pod for every HTTP request. Argo can execute those requests through
the Workflow's Agent pod. This Argo Agent is unrelated to a kagent `Agent`.

### Completion is not deletion

By default, Argo does not immediately delete completed Workflow pods. Configure
`spec.podGC` when the controller should remove them. Configure
`spec.ttlStrategy` when the completed Workflow object should later be removed.
These settings solve different retention problems.

```yaml
spec:
  podGC:
    strategy: OnPodCompletion
    deleteDelayDuration: 30s
  ttlStrategy:
    secondsAfterCompletion: 3600
```

Choose retention long enough to preserve the logs and evidence needed for
evaluation and incident diagnosis.

### DeepEval prompt count does not equal pod count

Running six DeepEval test cases does not, by itself, start six pods. Pod count
depends on how the evaluation runner and target agent are deployed:

In this repository's recommended DeepEval shape, one `deepeval test run`
command executes the whole test suite inside one CI runner, Argo script step, or
Kubernetes Job. Five or six cases therefore mean one evaluation-runner pod when
run in Argo, plus five or six calls to the already deployed target agent. They
do not mean five or six target-agent pods.

| Evaluation layout | Likely pod behavior for six prompts |
| --- | --- |
| One local or long-running DeepEval runner calls a normal kagent `Agent` | No new target pods; all prompts reuse the existing agent pod or replicas |
| One Argo container or script node loops over all six prompts | One caller pod; the existing target agent pod is reused |
| Argo fans out six container or script nodes | Up to six caller pods, depending on parallelism; the existing target agent pod is reused |
| Argo uses six `http` template nodes in one Workflow | Requests use the Workflow-scoped Argo Agent pod; this is not six target agent pods |
| The harness creates one Kubernetes Job per test case | Six Job pods, subject to scheduler concurrency and cleanup policy |
| Six isolated `SandboxAgent` chat sessions | Six logical actors, not six new Kubernetes pods; active calls consume WorkerPool slots |

Parallel prompts can increase load and may cause a Deployment or cluster
autoscaler to add replicas, but that is a scaling decision rather than a
one-prompt-one-pod rule. For comparable evaluations, record test concurrency,
session reuse, target replica count, actor count, and caller pod count alongside
the scores.

## SandboxAgent on Agent Substrate

### Preparation and request path

```text
GitOps applies SandboxAgent
        |
        v
kagent creates an ActorTemplate
        |
        v
Substrate creates a golden snapshot

WorkerPool keeps a smaller number of worker pods ready

first request for chat session
        |
        v
create logical actor from the current ready template
        |
        v
restore actor into a free worker pod
        |
        v
run A2A request and return response
        |
        v
checkpoint and suspend actor
        |
        v
release worker for another actor
```

The logical actor belongs to the chat session. The next prompt in that session
resumes the same actor from its last snapshot. A new session gets another
actor. The actors can outnumber the worker pods because only active actors need
a worker slot.

Current kagent A2A transport suspends a `SandboxAgent` actor after the client
finishes reading the response body. This means the actor can be suspended
between two turns in an open UI chat. The user does not need to close the chat
first.

### API and Argo lifecycle

An API caller supplies the A2A `contextId`. For the first request with that ID,
kagent creates an actor from the current ready `ActorTemplate`. Substrate starts
the actor from the golden snapshot on a free worker. For later requests, kagent
resumes the same actor from its latest snapshot.

After the client consumes or closes the streaming response, kagent schedules a
suspend operation. Substrate captures the actor's memory and disk, stores the
snapshot, wipes the worker, and returns the worker to the pool. The Argo caller
pod then follows the Workflow's separate cleanup policy.

Use one new `contextId` per independent triage request. If an Argo retry must
continue the same analysis, reuse the original ID deliberately. Do not use one
fixed ID for unrelated incidents because that joins their agent state.

### UI lifecycle

The UI creates a kagent session for a new chat and uses its ID as the A2A
`contextId`. Each `SandboxAgent` chat therefore gets a separate actor.

The actor does not need to remain active while the user reads the answer. It
can suspend as soon as the response stream closes, even if the browser tab
remains open. The next message resumes the same actor and restores its saved
memory and disk.

Closing the browser does not delete the session or actor. When the user deletes
the kagent session, the controller deletes the session row and makes a
best-effort request to delete its actor. Deleting the `SandboxAgent` cleans up
all actors and generated templates that it owns. Neither operation deletes the
platform-owned `WorkerPool`.

Actor deletion and snapshot deletion are separate concerns. The current
Substrate architecture states that snapshot garbage collection is not yet
implemented. Treat stored snapshots as retained sensitive data until the
installed version and storage policy prove their removal.

### Benefits

- Idle sessions release worker memory and CPU.
- Restoring a snapshot avoids a full pod schedule and application boot.
- Memory and filesystem state can survive suspension.
- A smaller worker pool can support many intermittently active sessions.
- The current kagent path uses a sandboxed actor rather than a plain agent
  container.

### Costs and limits

- The platform must operate the Substrate control plane, networking, worker
  pool, and snapshot storage.
- Worker pods and the Substrate services still have a standing cost.
- Concurrent requests need enough free workers. A request can fail or wait when
  the pool has no capacity, depending on the installed version and caller.
- Snapshot confidentiality, integrity, retention, and deletion need explicit
  controls.
- Actor deletion might not remove snapshot bytes immediately. Verify the
  installed version's garbage-collection behavior.
- Debugging crosses kagent, the Substrate control plane, the router, the worker,
  and snapshot storage.
- The APIs are changing faster than standard Kubernetes workload APIs. Pin and
  test a compatible kagent and Substrate version pair.

## OpenClaw or Hermes AgentHarness

An `AgentHarness` is a managed remote environment for an OpenClaw or Hermes
coding agent. Every current `AgentHarness` uses Agent Substrate.

```text
GitOps applies AgentHarness
        |
        v
kagent creates a per-harness ActorTemplate and golden snapshot
        |
        v
first UI chat connection creates or resumes one shared actor
        |
        v
kagent proxies A2A/UI traffic to ACP over WebSocket
        |
        v
OpenClaw or Hermes runs multiple ACP chat sessions in the shared actor
```

### What happens when the UI chat closes

In the current implementation, closing the UI connection closes the WebSocket
but intentionally leaves the shared harness actor running. This supports users
who switch among several chats without repeatedly suspending the whole harness.

The UI has an explicit suspend action. Suspension checkpoints the shared actor
and releases its worker. Because all chats use the same harness actor,
suspending it affects every open chat for that harness. The next connection or
explicit resume action restores the actor.

Deleting one conversation is not the same as deleting the shared harness
actor. Delete the `AgentHarness` when the platform should remove the managed
environment. The harness finalizer cleans up the owned actor and generated
template. It does not delete the platform `WorkerPool`.

### Benefits

- OpenClaw or Hermes gets a persistent remote coding environment.
- Several chats can share one prepared backend and filesystem.
- ACP provides one UI path for streaming, cancellation, and tool approvals.
- Explicit suspension can preserve the environment while releasing its worker.

### Costs and limits

- One shared actor means that chats share the harness process and environment.
- Suspending one harness interrupts every chat that depends on that actor.
- Leaving the UI does not release the worker automatically in the current
  implementation. Operating policy or automation must decide when to suspend.
- Long-running commands and messaging-channel connections complicate automatic
  idle detection.
- The same Substrate control-plane and snapshot-storage requirements apply.

## Comparison

| Question | Normal `Agent` | Job per request | `SandboxAgent` | `AgentHarness` |
| --- | --- | --- | --- | --- |
| Pod starts on first prompt | No | Yes | No new per-request pod | No new per-request pod |
| Compute before first prompt | Agent pod | None, apart from platform services | WorkerPool pods | WorkerPool pods and prepared template |
| Unit created for a chat | Session record | Usually a Job and pod | Per-session actor | ACP session inside one shared actor |
| State after one response | Pod remains running | Process exits | Actor checkpoints and suspends | Shared actor remains running until suspended |
| Closing the browser stops compute | No | Not relevant | Not required for per-turn suspension | No |
| Normal cleanup operation | Delete or scale the Agent | Job TTL or delete Job | Delete session or SandboxAgent | Suspend or delete AgentHarness |
| State across idle time | External store or durable volume | External store | Actor snapshot | Shared actor snapshot after suspension |
| Best fit | A few busy service-style agents | Bounded one-shot work | Many intermittent declarative sessions | Stateful OpenClaw or Hermes environments |

## Which model to choose

Use a normal `Agent` when you have a small number of frequently used agents and
want the simplest Kubernetes operating model.

Use a Job when the work has a clear end, does not need an interactive process,
and benefits from one pod per execution. Argo Workflows can own this lifecycle
for platform tasks.

Use a `SandboxAgent` when many chat sessions are idle most of the time, session
state must survive idle periods, or the actor sandbox is a requirement.

Use an `AgentHarness` when OpenClaw or Hermes needs a persistent coding
environment, ACP chat, and optional messaging channels. Define a suspend policy
before using many harnesses. Closing a browser is not that policy.

Do not adopt Agent Substrate only to remove one or two idle pods. Its control
plane and snapshot services can cost more than the pods saved at small scale.
Measure the standing worker footprint, active concurrency, restore latency,
snapshot size, and idle-agent count before deciding.

## What to verify on an installed cluster

The upstream APIs are moving. Verify the installed CRDs, controller image, and
runtime behavior before relying on this page for a production design.

For a normal agent, inspect the Deployment and confirm that it stays available
while no chat is open:

```bash
kubectl -n {{KAGENT_NAMESPACE}} get agent {{AGENT_NAME}} -o yaml
kubectl -n {{KAGENT_NAMESPACE}} get deploy,pod,svc
```

For a sandboxed agent or harness, inspect the generated template, workers, and
actor state before, during, and after one harmless request:

```bash
kubectl -n {{KAGENT_NAMESPACE}} get sandboxagent,agentharness,actortemplate
kubectl -n {{KAGENT_NAMESPACE}} get workerpool
kubectl ate get actors -a {{ATESPACE}}
kubectl ate get workers
```

For a Job-per-request design, confirm that the TTL controller removes both the
Job and its dependent pod:

```bash
kubectl -n {{WORK_NAMESPACE}} get jobs,pods --watch
```

For an Argo caller, inspect the Workflow node types and cleanup policies instead
of inferring pod count from prompt count:

```bash
kubectl -n {{WORK_NAMESPACE}} get workflow {{WORKFLOW_NAME}} -o yaml
kubectl -n {{WORK_NAMESPACE}} get pods -l workflows.argoproj.io/workflow={{WORKFLOW_NAME}}
```

## Sources

This explanation was checked against the following upstream documentation and
source on 2026-09-11:

- Kagent agents and deployment-backed agents:
  https://kagent.dev/docs/kagent/concepts/agents/
- Kagent Agent Substrate concepts:
  https://kagent.dev/docs/kagent/concepts/agent-substrate/
- Kagent `SandboxAgent` walkthrough and per-session suspend behavior:
  https://kagent.dev/docs/kagent/examples/agent-substrate/
- Kagent `AgentHarness`, OpenClaw, Hermes, and shared ACP sessions:
  https://kagent.dev/docs/kagent/concepts/agent-harness/
- Current kagent A2A transport that suspends a `SandboxAgent` after a response:
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/go/core/internal/a2a/substrate_sandbox_transport.go
- Current kagent session-to-actor mapping and suspend behavior:
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/go/core/pkg/sandboxbackend/substrate/agent_actor.go
- Current kagent mapping from A2A `contextId` to the session ID:
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/python/packages/kagent-adk/src/kagent/adk/converters/request_converter.py
- Current kagent session deletion and actor cleanup:
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/go/core/internal/httpserver/handlers/sessions.go
- Current kagent harness gateway and explicit session lifecycle handlers:
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/go/core/internal/httpserver/handlers/agentharness_gateway.go
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/go/core/internal/httpserver/handlers/agentharness_session.go
  https://github.com/kagent-dev/kagent/blob/446cfcf7104f309e782ab87d20cd72306d98f150/go/core/pkg/sandboxbackend/substrate/agentharness_actor.go
- Agent Substrate architecture and actor lifecycle:
  https://github.com/agent-substrate/substrate/blob/main/docs/architecture.md
- Kubernetes Deployments:
  https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- Kubernetes Jobs and TTL cleanup:
  https://kubernetes.io/docs/concepts/workloads/controllers/job/
- Argo HTTP templates and the Workflow-scoped Argo Agent pod:
  https://argo-workflows.readthedocs.io/en/latest/http-template/
- Argo pod garbage collection and cost controls:
  https://argo-workflows.readthedocs.io/en/release-3.7/cost-optimisation/
- Argo Workflow fields, including `podGC` and `ttlStrategy`:
  https://argo-workflows.readthedocs.io/en/release-3.5/fields/
- This repository's DeepEval runner and rollout design:
  ../../observability/agent-evals/deepeval/README.md

The live receipts in the adjacent `agent-substrate` bundle prove an earlier
version pair in a lab. They do not prove that the current upstream lifecycle is
running on a workplace cluster.
