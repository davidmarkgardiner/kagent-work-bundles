# Run the live Kubernetes and GitLab example

The homelab demo can run a real model with real Kubernetes and GitLab reads. `tools.mode: live` deploys separate MCP services and changes the demo agent and UI to live-data mode. It uses no fixture model or fixture tool server. The fixture scenarios remain available through `tools.mode: fixture`.

## Live architecture

```text
HTTPS UI → dashboard → kagent session → Substrate actor
                                      → agentgateway → real model
                                      → Kubernetes MCP → actual Kubernetes API
                                      → GitLab MCP → actual GitLab project API

native runtime, gateway, and MCP spans/logs → collector → UI
```

The app, collector, model gateway, and both MCP servers run on one cluster. The model provider and GitLab API can be external services. The Kubernetes data is the actual demo namespace. The GitLab data is an existing approved sandbox project. Reading these two sources does not establish that the GitLab project built the Kubernetes deployments.

## Pick a live scenario and inspect the actual tool

The UI offers **Live Kubernetes workload check**, **Live GitLab pipeline review**, and **Live Kubernetes + GitLab inspection**, plus a custom prompt. These invoke the real registered tools. The Kubernetes preset uses the Helm release namespace; the GitLab server remains fixed to its privately configured project.

The Kubernetes MCP and GitLab MCP panels light up separately when their completed **MCP execution spans** arrive. Each panel shows the latest exact tool, completed-call count, duration, and exported OTel status for the selected workflow. Select a panel or operation to inspect the original span, service, trace, and metadata. The shared request topology can stay the same while these panels show which MCP actually handled a tool call.

A client span proves an attempt and is labelled accordingly. A completed server span shows server execution. The pinned Kubernetes MCP 0.3.0 emits `mcp.tool.TOOL` handler spans as internal spans: only the exact registered Kubernetes service, allowlisted tool, and matching operation name qualify for its separate **MCP handler completed (internal span)** label. Arbitrary internal spans do not qualify. An unset OTel status is displayed as **status not reported**, rather than success. Highlights reflect completed spans received by the collector, so they can appear after the tool finishes. They do not claim to measure in-flight execution.

Kubernetes tool names arrive in `mcp.tool.name` on service `flow-kubernetes-mcp`; GitLab uses `gen_ai.tool.name` on `flow-gitlab-mcp`. Kubernetes currently exports tool spans, not native tool log records. In the **Logs** tab, GitLab emits tool/API metadata and the gateway emits access records. The UI keeps these logs separate from spans and omits request/result bodies.

## Configure the source deployment

1. Build the current source through the normal image pipeline. No container archive is needed.
2. Populate one private values file with the selected local or AKS Istio ingress, the real-model configuration from `live-model.yaml.example`, and the settings in `live-tools.yaml.example`.
3. Provide existing model and GitLab Secrets through the approved credential process. Use a project-scoped credential with the least approved read permissions for ongoing use. Do not commit the project path, credential values, or filled operator file.
4. Run the preflight/deployment procedure in WORK-BUNDLE-README.md. The existing-agent profile remains preferable when workplace agents and MCP servers already exist. Do not replace those resources with the dedicated homelab example.

The Kubernetes MCP uses the digest-pinned kagent tools 0.3.0 image. Its CLI registers the `k8s` provider with `--read-only`. The AgentTemplate exposes only `k8s_get_resources` and `k8s_get_events`. A dedicated ServiceAccount has only `get` and `list` for deployments, replicasets, pods, services, and events in the release namespace. It has no Secret, node, cross-namespace, or write permissions. This one MCP pod needs its scoped service-account token; other application pods do not mount one.

The GitLab MCP is `live_gitlab.py` in the application image. It exposes only `gitlab_get_project`, `gitlab_list_issues`, and `gitlab_get_latest_pipeline`. Every operation is a fixed HTTPS GET for the configured project. It accepts no project, URL, query, or write arguments from the agent and follows no redirects. Responses are bounded to 256 KiB in transport and 8 KiB after projection. Issue output is limited to five metadata records and 160 characters per title. Pipeline output is limited to one record. Descriptions, comments, tokens, and raw results are not exported to OTel.

## Use the UI

Open the approved HTTPS URL. Confirm the banner says **Live model and real read-only Kubernetes and GitLab MCP data**. Fixture presets are hidden. The prompt is prefilled with the actual read-tool names and configured namespace. Send it and follow the tool cards as spans arrive.

Switch to Logs and select `flow-gitlab-mcp` in the Service filter to inspect its MCP operations and API reads. The filter is applied before the 200-record display limit. Kubernetes MCP tool spans are visible in the visual timeline even when that server does not export OTel logs. Select a card to inspect the original span and its native parent.

The native Substrate restore/checkpoint/suspend sequence is independent evidence of runtime execution. Token counts are reported when available. USD remains an explicit estimate or unknown. Entra authentication and per-agent authorization are separate from this live read demonstration.

## Verify both servers in one invocation

Use the private reviewed prompt file and actual server/tool names:

```bash
python3 scripts/verify-https.py \
  --url 'https://{{DEMO_FQDN}}' \
  --prompt-file '{{PRIVATE_READ_ONLY_PROMPT_FILE}}' \
  --expect-mcp flow-kubernetes-mcp:k8s_get_resources \
  --expect-mcp flow-gitlab-mcp:gitlab_get_project \
  --expect-mcp flow-gitlab-mcp:gitlab_list_issues \
  --expect-mcp flow-gitlab-mcp:gitlab_get_latest_pipeline \
  --context '{{APPROVED_KUBE_CONTEXT}}' \
  --output '{{PRIVATE_EVIDENCE_DIRECTORY}}/live-tools.json'
```

The verifier requires successful tool spans from each named server, a completed agent reply, all eight component roles, native restore/checkpoint, and a final suspended actor. It rejects spans labelled simulated. Compare returned deployment names, issue IIDs, and pipeline ID with independent Kubernetes and GitLab reads. Keep private project data out of public receipts.

## Credential lifecycle and rollback

The initial homelab proof reused the existing GitLab CLI OAuth session after its normal refresh. Only the short-lived access token was copied into a Kubernetes Secret. The token's permissions may be broader than the adapter's three fixed read capabilities. No refresh token was copied and no GitLab project content was changed. This is not an unattended credential-renewal proof.

For a continuing demo, supply a separately managed read-only project credential. When its Secret value changes, restart only the GitLab MCP Deployment so its environment receives the new token. Missing or expired credentials return a real read error. The server never substitutes fixture data. Provider credentials remain in the existing model Secret.

To return to rehearsal, deploy the fixture values and the original model mode through the same release. This removes the chart-owned live MCP resources and scoped Role. Existing external Secrets remain. Do not delete platform namespaces, GitLab projects, or the shared kagent/Substrate installation.

The saved final receipt used an in-cluster HTTPS client because local kubectl port-forward reset during blocked-endpoint probes. Its test process resolved the certificate hostname `localhost` to `flow-https` while retaining TLS/SNI and CA/hostname validation. No runtime application route or security policy was bypassed. The laptop UI/API checks separately used https://localhost:9443. Use the real routable HTTPS hostname for AKS acceptance.

The pinned upstream handler instrumentation uses the default internal span kind: https://github.com/kagent-dev/tools/blob/v0.3.0/internal/telemetry/middleware.go . This adaptation is specific to the bundled Kubernetes MCP; verify other internal-span emitters before adding an evidence rule.
