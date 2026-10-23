# kagent BYO languages and framework integration

BYO agents can use languages beyond Go and Python. Compatibility depends on the
runtime protocol and lifecycle integration, not the implementation language.
This README records the integration choices and requirements for a later example.
It contains no runnable TypeScript, C# or LangGraph adapter and proves no deployment.

Download the full GitHub repository ZIP and copy this folder into the workplace
repository. The folder is published at
https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/kagent-byo-language-support.

## Language and framework choices

| Choice | Integration path | Evidence boundary |
| --- | --- | --- |
| Go | Official kagent helper and a custom executor | Existing helper, still requires target testing |
| Python | Official helpers with framework-specific behavior | Helper choice and release compatibility matter |
| TypeScript or JavaScript | Custom container and compatible gRPC adapter | Feasible integration path, no implementation supplied here |
| C#, Java or Rust | Custom container and compatible gRPC adapter | Feasible integration path, no implementation supplied here |
| LangGraph or LangChain | Framework behind a compatible agent adapter | A framework is separate from its transport and lifecycle wrapper |

These are integration routes, not a claim that kagent ships equally complete SDKs
or tested examples for every language. The official BYO guide describes Go/Python
helpers and direct implementation in other languages at
https://www.kagent.dev/docs/kagent/1.x/agents/bring-your-own-agent/.

## Version-specific contract

The 1.x documentation describes a BYO container serving A2A gRPC on port `80` and
HTTP `GET /readyz` on port `8081`. It requires an explicit command and an image
pinned by digest. The image consumes the supplied configuration as needed.

The older 0.x LangGraph example uses a different BYO resource and JSON-RPC path.
Its wrapper is not a drop-in 1.x runtime. Current 1.x documentation also identifies
JSON-RPC-only LangGraph, CrewAI and OpenAI adapters as incompatible with that
gRPC contract. The older example remains documented at
https://kagent.dev/docs/kagent/0.x/examples/langchain-byo/.

The checked source reference is `v1.0.0-alpha17`, not a workplace upgrade target.
Discover the installed image, served API and runtime before selecting a wrapper.
The tagged compiler advertises gRPC at port `80`:
https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/core/internal/translator/byo/compiler.go.

## Task persistence is part of the adapter

Exposing gRPC and readiness alone is insufficient for a native durable runtime.
The tagged architecture requires private TaskStore integration for task creation,
progress and completion. A stock A2A server backed only by an in-memory task store
does not meet that requirement. Official helpers handle parts of this integration.
The source contract is recorded at
https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/docs/architecture/configuration-and-compilation.md.

For a custom adapter, acceptance needs actual controller-visible task and context
identities, terminal results, cancellation and supported continuation. Readiness
cannot establish those behaviors. Any advertised approval, memory, skills or
telemetry capability also needs its own observed result. No feature is assumed
to work merely because the framework exposes it locally.

## Dapr coordinator versus kagent-hosted agent

For the proposed Kafka triage replacement, the coordinator can remain a separate
application written in the selected Dapr SDK's supported language. It calls the
existing kagent agents through their public A2A route. That choice needs a client,
not a kagent BYO server. Dapr Workflow SDK support must be checked for the chosen
language and pinned release independently.

A kagent-hosted TypeScript or C# agent is a different scope. Its container must
implement the native runtime contract, including TaskStore and lifecycle behavior.
That is useful when kagent should host and expose the custom agent itself.

The coordinator's intake, concurrency and retry boundaries remain in the
separate Dapr design:
https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/dapr-kagent-triage.
Changing agent language does not solve Kafka overload or authorize per-event
Agent/Harness creation.

## Proposed runnable example scope

A later implementation starts with one selected language and exact target
version. Its first executor returns deterministic text without model or tool
calls. This isolates protocol and task persistence from framework behavior.

The delivery sequence is a proposed acceptance plan.

1. Generate protocol clients and servers from the exact pinned definitions.
   Implement readiness, runtime configuration and native task persistence.
2. Build an approved container and render the version-specific BYO resources.
   Keep deployment and any Substrate prerequisites explicit.
3. Invoke through the real kagent gateway. Read the actual native task result
   and verify conversation continuity and terminal publication.
4. Exercise a supported restart or suspend/resume and cancellation. Record
   failures and unsupported behavior without replacing missing proof with Ready.
5. Add the chosen framework and approved model route only after the deterministic
   contract passes. Verify bounded model use, tools, approvals and telemetry
   separately before advertising those capabilities.

No LangGraph wrapper is implemented by this plan. A TypeScript example would not
establish C# compatibility, and a deterministic reply would not prove agentic
reasoning or safe arbitrary tool execution.

## Configuration for an eventual implementation

| Placeholder | Required input |
| --- | --- |
| `{{KAGENT_VERSION}}` | Exact installed release and served APIs |
| `{{TARGET_NAMESPACE}}` | Approved isolated example namespace |
| `{{APPROVED_IMAGE_DIGEST}}` | Reviewed container at an immutable digest |
| `{{RUNTIME_PROFILE}}` | Compatible Harness and runtime dependencies |
| `{{KAGENT_A2A_ROUTE}}` | Approved caller route and authentication |
| `{{APPROVED_MODEL_CONFIG}}` | Existing approved model route, only for a later model-backed stage |

Keep real endpoints, identities, credentials and invocation evidence outside this
public folder. Follow the normal Flux delivery and target authorization process.
This handoff adds documentation only and changes no running agent or cluster.
