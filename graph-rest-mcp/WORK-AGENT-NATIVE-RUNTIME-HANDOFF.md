# Build the Graph REST MCP POC without Substrate

**Work-agent instruction, updated 29 October 2026.** This sheet supersedes the
previous Harness investigation. Substrate is blocked. Do not create or repair
Harness, AgentHarness, WorkerPool, SandboxTemplate, SandboxAgent, or snapshot
infrastructure. Their absence is expected and is not a gate for this POC.

## Build a standalone model-to-MCP client

Use the current cluster and the already verified adapter. Run a small bounded
client as an ordinary Kubernetes Job, or on an existing approved execution host.
Use the existing authorized POC delivery process. Do not create a native alpha3
Agent or change shared platform resources.

```text
Approved question -> bounded client -> existing model Gateway
                           | model requests get_graph_context
                           v
                    existing MCP adapter -> existing REST service
                           | real tool result
                           v
                    model -> grounded answer
```

1. Preserve the adapter image, endpoint, private REST settings, authentication,
   TLS, and existing network controls. Reuse the approved model route. Confirm
   permitted connectivity from the client to MCP and the model Gateway.
2. Implement a small client using approved installed libraries and the actual
   provider protocol. Use the existing image if suitable. If another client image
   is needed, build and scan it through the approved process. Do not download
   packages into the running workplace pod or require loose wheel imports.
3. Initialize Streamable HTTP MCP and list tools using a real MCP client.
   Expose only the discovered `get_graph_context` schema to the model. Require
   retrieval for supported graph questions. Validate the model's requested tool
   name and typed arguments before execution. Do not substitute a direct REST
   call, manufacture a tool request, or prefill a canned answer.
4. Allow at most one graph tool call and two model requests per question.
   Execute the requested tool through MCP. Pass its actual bounded result back
   to the model using the provider's tool-result protocol. Ask for a final answer
   grounded in returned facts, relationships, source, scope, and limitations.
5. Reject unknown tools, invalid arguments, or additional call requests. Keep
   finite deadlines and the adapter's existing limits. Treat tool output as data.
   Ambiguous or unsupported results require clarification or an honest limitation.
   On errors, report data unavailable. Do not retry or switch providers after a
   failed or uncertain submission.
6. Keep the client private and read-only. Use existing approved credential mounts,
   no pod API token, and no SQL, shell, file, or write tools. Keep credentials and
   private responses out of public artifacts and logs.

## Prove the model uses the tool

Run one approved known-answer graph question and one ambiguous or unsupported
question. Test upstream failure behavior with an approved mock. For the supported
question, require an actual model-requested MCP call and a correct grounded answer.
Missing retrieval is a failed case, not a pass.

Return the client source, configuration or Job manifest, image digest if built,
checks, sanitized receipts, and rollback or cleanup for only the new POC objects.
Record actual tool name, result status, counts, source, scope, and answer
correctness. The existing `scripts/mcp_acceptance.py` has fixture-specific oracles;
do not run its synthetic facts unchanged against the workplace API.

Report `STANDALONE MODEL-MCP POC VERIFIED` only after this flow passes. Report
native alpha3 invocation separately as `DEFERRED: SUBSTRATE UNAVAILABLE`.
A direct MCP call alone does not prove model integration. If another prerequisite
fails, name that model, network, image, or authorization gate precisely.

## Keep native kagent integration separate

Native `api.kagent.dev/v1alpha3` execution still requires Harness and Substrate.
This standalone POC does not bypass or verify that runtime. If native invocation
is subsequently required, the existing cluster serving `kagent.dev/v1alpha2` can
use a normal Deployment-backed declarative Agent without Substrate. Confirm the
served API and working Deployment pattern first; a cluster nickname such as
“alpha2” is insufficient. Do not switch clusters or install a new platform to
complete the standalone proof above.

References: [alpha3 Harness requirements](https://kagent.dev/docs/kagent/1.x/agents/agent-harness/)
and [legacy Deployment-backed Agents](https://kagent.dev/docs/kagent/0.x/concepts/agents/).
