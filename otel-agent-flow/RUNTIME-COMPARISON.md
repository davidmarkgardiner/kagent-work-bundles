# Compare execution with and without Substrate

Select **Agent runtime** in the prompt column, then run the same live scenario through each option. The default bundled profile supplies both options. The model, gateway, instructions, MCP endpoints, and tool allowlists are shared.

| Demonstration | Execution | Expected received flow |
|---|---|---|
| Without Substrate | Native kagent Go ADK in the normal `flow-standalone` Deployment | Caller, kagent runtime, agentgateway, model, and actual MCP tool execution. Substrate, worker, and actor remain inactive. |
| With Substrate | kagent Session API and the existing dedicated `flow-demo-agent` Harness | The same model/tool flow plus native Substrate actor resume, worker restore, checkpoint, and suspend. |

The last eight requested trace IDs are preferentially retained within the existing trace/span memory limits. Requested runs appear before background platform traces. A runtime selection changes the next request. Each trace retains the runtime that actually handled it, so selecting a historical trace does not relabel it. Missing telemetry remains missing; a client attempt does not confirm MCP execution. Kubernetes currently exports tool spans; GitLab also exports tool/API logs.

## What standalone means here

The installed kagent 1.0.0-alpha8 Harness API requires Substrate. The standalone demonstration therefore runs the **same pinned native kagent Go ADK libraries** in a normal Deployment. It is not a second controller-managed Harness or Agent CR.

The wrapper uses the native runner, executor, A2A server, and Google ADK in-memory sessions. It deliberately does not use `app.New`, whose central TaskStore requires controller/actor identity. It has no controller URL, actor token, Kubernetes service-account token, skills, plugins, stdio tools, central memory, or Substrate configuration. Its model credential is the same non-secret gateway client value; the gateway retains the real provider credential. Its intended egress is only the shared gateway, MCP servers, collector, and DNS.

The standalone process has in-memory sessions and tasks. Pod replacement clears them. It demonstrates independent execution, not Substrate persistence, snapshotting, sandboxing, or Entra isolation. The bundled native `ask_user` tool can request input; the caller treats that as incomplete and never automatically approves it.

Pinned source and dependency behavior:

- https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha8/go/adk/pkg/runner/adapter.go
- https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha8/go/adk/pkg/a2a/server/server.go
- https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha8/go/adk/pkg/app/app.go

The Docker build checks out commit `b8d8b5ca7dd2cc4fba9ab1cc5c2b4b40536d0bf2` in its builder stage and uses that module's locked dependencies and replacements. The public bundle contains only the small wrapper. CI needs the reviewed Go builder image, upstream Git source, and Go dependencies through approved upstreams or internal mirrors.

## Deployment modes

Set `execution.mode` in the reviewed operator values before preflight:

- `both` deploys both paths and enables the runtime picker. This is the bundled default.
- `standalone` deploys only the normal ADK Deployment and shared app/gateway/tools. It creates no kagent or Substrate custom resources and preflight does not query their CRDs, WorkerPools, or Helm releases. No Substrate or kagent controller installation is required for this mode.
- `substrate` keeps only the original Substrate path.

The small overlays in `deploy/values/comparison.yaml` and `deploy/values/standalone.yaml` show the mode and display label. Copy the appropriate settings into the single filled operator values file used by preflight. Keep the same reviewed image digest, model/tools settings, Secret references, and HTTPS ingress inputs. AKS still serves the dashboard through the existing Istio Gateway and VirtualService.

The `integration.mode: existing` profile continues to reuse the existing Substrate-backed agent and does not create a new standalone Deployment. Use bundled comparison mode for the two dedicated demonstration agents; do not replace workplace agents or their model/tool wiring.

## Evidence gates

Run the approved read-only prompt with `scripts/verify-https.py --runtime standalone --execution-mode standalone` and its normal prompt, CA, and expected MCP arguments. The verifier requires a completed native standalone invocation, gateway/model/MCP execution, and no actor or Substrate activity in that request.

Repeat with `--runtime substrate --execution-mode substrate`. That path must also supply native restore/checkpoint and a final suspended actor. A configured Deployment or ready MCP endpoint alone is not a passed demonstration. NetworkPolicy enforcement and AKS runtime behavior still require checks on the target CNI and cluster.

The current homelab comparison and its exact test scope are recorded in [portable-runtime-comparison-verification.json](evidence/portable-runtime-comparison-verification.json). The UI behavior receipt is [portable-runtime-ui-verification.json](evidence/portable-runtime-ui-verification.json).
