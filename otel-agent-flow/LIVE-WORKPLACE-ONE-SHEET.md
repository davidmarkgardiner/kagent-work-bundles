# Connect the OTel demo to real workplace data

Work from the `otel-agent-flow/` bundle root. Deliver one fresh, read-only request through the approved model route and Kubernetes MCP, with independently checked results and correlated OTel evidence. Keep workplace configuration and receipts private. Use the workplace's authorized deployment process.

## Establish what is running

Inspect effective release values, generated dashboard configuration, selected Agent and image digests. Record the source revision and rollback configuration privately. Do not infer mode from repository defaults or a UI label.

| Configuration | Model calls | Tool data |
| --- | --- | --- |
| `integration.mode: bundled`, `model.mode: fixture`, `tools.mode: fixture` | Fixture model endpoint | Simulated |
| Bundled with `model.mode: live`, `tools.mode: fixture` | Real configured provider | Simulated |
| Bundled with both model and tools set to `live` | Real configured provider | Real Kubernetes and GitLab reads |
| `integration.mode: existing` | Selected agent's ModelConfig and gateway route | Selected agent's configured tools; verify their backends |

The chart defaults to fixtures. Real runtime execution and OTel spans can carry synthetic model responses or tool results. Recorded live lab runs do not establish yesterday's workplace mode.

## Collect prerequisites before changes

- Record the installed kagent version, served API, agent type, controller endpoint and readiness. For Substrate, check Harness and WorkerPool health. The bundled baseline is kagent `1.0.0-alpha8` with Substrate `0.4.0-alpha1`. Do not upgrade work to fit it.
- Select the approved ModelConfig, gateway route and managed credential references. Confirm the intended real model and invocation budget.
- Select one cluster and namespace. Discover actual MCP tools, backend cluster identity and effective permissions. Permit bounded workload/event reads. Exclude Secrets, mutation and arbitrary shell. Use the approved MCP identity for cluster access.
- Identify internal image digests, authenticated HTTPS ingress, CA trust, OTLP routes and network-policy peers. GitLab is optional for the first existing-agent proof.

## Implement the smallest live integration

1. Prefer [the existing-agent values](deploy/values/existing-agent-istio.yaml.example) and [LIVE-INTEGRATION.md](LIVE-INTEGRATION.md). Set `integration.mode: existing`, `integration.existingAgent`, `agentNamespace` and the controller address when required. Preserve the selected agent's ModelConfig, gateway, credentials and tool ownership. The chart does not create those resources in this mode.
2. Check the invocation contract. This profile uses a Substrate-backed agent. An ordinary `kagent.dev/v1alpha2` Agent needs reviewed A2A wiring and acceptance changes; the backend already contains an A2A client path. `execution.mode: standalone` selects the bundle's own Go ADK Deployment, not an arbitrary existing ordinary Agent. Report incompatibilities.
3. Reuse compatible dashboard, collector and MCP images. Connecting an existing live agent does not itself require new images. Build/import only missing components or changed code. Follow [IMAGE-IMPORT-SHEET.md](IMAGE-IMPORT-SHEET.md).
4. Render a separate release/namespace. Converting the bundled release in place can remove its chart-owned agent, gateway and tools. Review the diff, policies and target schemas before rollout.
5. Add OTel exports through platform configuration while preserving existing destinations. Include agent/runtime, gateway, instrumented MCP and applicable Substrate lifecycle telemetry. Set `collector.sourceNamespaces`. Verify W3C context and parent IDs. Export bounded metadata; exclude prompts, credentials and result bodies.
6. Request a discovered read tool against the selected namespace. Independently compare workload names and status with approved Kubernetes reads. Confirm the MCP queried the intended cluster.

## Prove completion and retain rollback

For the supported Substrate existing-agent route, run the supplied verifier with private, reviewed inputs:

```bash
python3 scripts/verify-https.py \
  --url 'https://{{DEMO_FQDN}}' \
  --prompt-file '{{PRIVATE_READ_ONLY_PROMPT_FILE}}' \
  --expect-mcp '{{ACTUAL_MCP_OTEL_SERVICE}}:{{ACTUAL_READ_TOOL}}' \
  --execution-mode substrate \
  --context '{{APPROVED_KUBE_CONTEXT}}' \
  --namespace '{{DEMO_RELEASE_NAMESPACE}}' \
  --output '{{PRIVATE_EVIDENCE_DIRECTORY}}/live-workplace.json'
```

Supply `--ca` and approved authentication where required. The verifier requires successful server tool spans, model/gateway activity and Substrate lifecycle. It rejects simulated tool spans. It is not an ordinary-agent verifier. Leave uninstrumented server evidence UNKNOWN rather than weakening checks.

Record PASS, FAIL, UNKNOWN or NOT RUN for provider completion, correct cluster/namespace reads, independent comparison, trace correlation, HTTPS/access controls, effective permissions and network-policy enforcement. The verifier alone does not prove all these controls. Backend failures must remain errors without fixture fallback. Label costs as reported, estimated or unknown; claim skill usage only with explicit runtime evidence.

Deliver the configuration diff, image digests, private receipt, independent read-back and remaining gaps. Roll back the demo release and added telemetry exports through the approved process. Preserve shared platform resources and existing observability routes.

Bundle source: https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/otel-agent-flow
