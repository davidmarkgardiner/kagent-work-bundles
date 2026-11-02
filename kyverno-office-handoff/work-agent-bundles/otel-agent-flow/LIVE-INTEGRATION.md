# Connect the demo to existing agents and real tools

Use `deploy/values/existing-agent-istio.yaml.example` for the workplace deployment. This profile creates the dashboard, collector, NetworkPolicies, and Istio VirtualService. It creates no Agent, Harness, ModelConfig, model Secret, MCP server, workflow service, or agentgateway. Existing routing and tool configuration stay with their owners.

## Select the approved agent

1. Choose a Ready, read-only Substrate-backed agent. Verify its Harness uses the approved WorkerPool and installed API version in PLATFORM-PREREQUISITES.md.
2. Put its name in `integration.existingAgent` and its namespace in `agentNamespace`. If necessary, set `integration.controllerAddress` to the existing in-cluster controller Service and gRPC port.
3. Keep the agent's existing ModelConfig and agentgateway route. Keep provider authentication and tool authorization in the current platform configuration.
4. Put the existing Istio Gateway's `namespace/name` in `ingress.istio.existingGateway`. Set the gateway namespace, selector, hostname, and existing TLS Secret consistently. The chart then owns only the VirtualService.
5. Add the actual gateway and MCP namespaces to `collector.sourceNamespaces` when they differ from the platform namespaces. Review the installed CNI's policy enforcement.

`deploy.sh` does not change platform Helm releases or OTel settings in existing-agent mode. Before showing live flows, use the platform's approved delivery configuration to fan out its existing traces and logs to the demo collector. Keep the existing observability destination. The bundled-mode telemetry helper is a reference for the pinned native export settings, not an instruction to overwrite work telemetry.

Send OTLP gRPC to `flow-collector.agent-flow-demo.svc.cluster.local:4317`, or OTLP HTTP to port 4318. Change the namespace when configured differently. Include native kagent, Substrate controller/worker/actor, and agentgateway exports. Include MCP server spans when that server supports OTel. Keep W3C trace context across tool requests and verify parent span IDs. An uninstrumented server stays unknown. A client tool span proves a call was attempted, not that the server completed it.

## Demonstrate Kubernetes MCP

Use the existing approved Kubernetes MCP server and a read-only specialist agent. Discover its actual tool names before writing the prompt. Give it a narrow target namespace and bounded output. For example, ask the agent to list workload status in the designated demo namespace and explain one condition using an allowlisted read tool. Do not grant mutation tools for this demonstration.

The existing UI shows received `gen_ai.tool.name`, `mcp.tool.name`, or `tool.name` metadata in trace details and logs. The map groups these under MCP tools. It does not draw a separate box for every Kubernetes object or infer successful execution from a prompt.

For a real tool with server instrumentation, prepare a private prompt file and run:

```bash
python3 scripts/verify-https.py \
  --url 'https://{{DEMO_FQDN}}' \
  --prompt-file '{{APPROVED_READ_ONLY_PROMPT_FILE}}' \
  --expect-tool '{{ACTUAL_READ_ONLY_TOOL_NAME}}' \
  --tool-service '{{ACTUAL_MCP_OTEL_SERVICE_NAME}}' \
  --context '{{APPROVED_KUBE_CONTEXT}}' \
  --output '{{PRIVATE_EVIDENCE_DIRECTORY}}/connected-verification.json'
```

Repeat `--expect-tool` for multiple required calls from the same service. The check requires the named server spans, the full native lifecycle, all eight component roles, and actual OTel logs. It rejects tool spans labelled simulated. It does not send fixture workflow instructions to an existing agent. If the MCP server has no OTel, report server completion as UNKNOWN and retain the observed client tool calls. Do not relabel client-only evidence to pass this gate.

## Include skills honestly

A skill is agent guidance or packaged code. Loading a skill is not automatically a network request or a separate agent. Keep the existing approved skill mount and agent instructions. The current diagram has no dedicated skill node.

Demonstrate a skill by asking a task that uses its guidance and inspect the resulting real tool calls. Attribute a skill execution only when the runtime exports a corresponding skill event or span. If explicit skill activity is required, have the work agent add runtime instrumentation for skill name, immutable version, start/end, and status with native trace context. Add those bounded metadata fields to the projection and tests. Never infer skill usage from a file mount or an assistant claim. Skill contents and tool-result bodies stay outside OTel logs.

## Record workplace acceptance

The local rehearsal proves fixture workflows and one live model using simulated tools. This existing-agent profile is rendered and checked offline. Real workplace Kubernetes MCP traffic, existing Gateway reconciliation, skills events, access controls, and policy enforcement require target-cluster receipts. Keep PASS, FAIL, UNKNOWN, and NOT RUN explicit.

Use a fresh release namespace for each integration mode. Switching an existing bundled release to existing-agent mode would remove its chart-owned demo agent, gateway, and tools. Review a migration separately. Keep the approved single-user audience boundary and private rollback state.

For multiple MCP servers in one invocation, use repeated `--expect-mcp SERVICE:TOOL` pairs instead of `--expect-tool` and `--tool-service`. See LIVE-HOMELAB.md for the combined real Kubernetes and GitLab example.
