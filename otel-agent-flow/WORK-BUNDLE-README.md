# Deploy the single-cluster workflow demo

Download the GitHub repository and use this folder as the work-agent bundle. No separately prepared ZIP or image archive is needed. Application code is shared between the local rehearsal and AKS. Change operator values, TLS integration, and registry references rather than copying the earlier host-tunnel setup.

## Architecture

```text
HTTPS browser → Istio ingress on AKS, or local TLS proxy
                  → dashboard → native kagent gRPC API
                                   → Substrate actor on WorkerPool
                                       → agentgateway → fixture or live model
                                       → existing Kubernetes MCP/tools, or fixture tools

caller + kagent + Substrate + gateway + tools
                  → in-cluster OTel collector → dashboard metadata projection
```

All application Services select pods in one namespace. kagent and Substrate run in their platform namespaces on the same cluster. A live model provider may be external. There are no host endpoints, SSH model tunnels, manually populated EndpointSlices, or host-mounted application files in the chart.

The application namespace defaults to `agent-flow-demo`. Platform namespaces default to `kagent` and `ate-system`. Choose the existing-agent profile to reuse the current kagent agent, agentgateway, model route, and MCP tools. Choose the bundled profile for a dedicated demo agent and simulated tools. The application pods have no Kubernetes service-account token. Existing MCP permissions stay with their owning deployment.

## Prepare

1. Check [PLATFORM-PREREQUISITES.md](PLATFORM-PREREQUISITES.md). The cluster needs the pinned platform, healthy gVisor workers, and snapshot storage.
2. Prepare the Python operator environment with `python3 -m pip install -r requirements-ops.txt`. kubectl, Helm 3, Docker, curl, and OpenSSL are also used by the relevant scripts.
3. Build the application from this repository using [IMAGE-IMPORT.md](IMAGE-IMPORT.md). Mirror upstream images/charts where public egress is unavailable.
4. For the current work platform, copy `deploy/values/existing-agent-istio.yaml.example` to a private operator directory and replace every placeholder. Configure the existing approved TLS Secret in `aks-istio-ingress`.
5. Configure the approved work authentication/access layer. The application is a shared demo, with one in-flight prompt and one user partition.

Read [LIVE-INTEGRATION.md](LIVE-INTEGRATION.md) for existing-agent telemetry fan-out, Kubernetes MCP, skills, and the connected verification command. The bundled alternative is `deploy/values/aks-istio.yaml.example`.

`deploy/values/local.yaml` runs the fixture model and local TLS proxy. The AKS example also starts in fixture mode. To use a real provider, merge the live-model example into the private operator values. The model credential must already exist in the application namespace; it is never embedded in chart values.

## Deploy on the selected cluster

```bash
export KUBE_CONTEXT='{{APPROVED_KUBE_CONTEXT}}'
export FLOW_NAMESPACE=agent-flow-demo
export FLOW_STATE_DIR='{{PRIVATE_ROLLBACK_DIRECTORY}}'
bash scripts/deploy.sh '{{PRIVATE_OPERATOR_VALUES_FILE}}'
```

The preflight reads the selected cluster without changing the current kubectl context. It checks served Agent APIs, chart versions, worker readiness, ingress prerequisites, TLS Secret, and a live-model Secret when applicable. Work deployments require an application image digest.

In existing-agent mode, the installer reconciles only the demo release and leaves platform releases and OTel settings unchanged. Configure approved telemetry fan-out before live verification. In bundled mode, it also configures native kagent/Substrate OTel exports. It preserves existing egress authorization and credential policies while enabling the missing egress tracing hop. Original values and egress configuration go into the private state directory. The script does not install or upgrade AKS, Istio, kagent, or Substrate to a new version.

For bundled mode, keep the Substrate egress delta in the platform's normal delivery configuration. The installer uses `scripts/substrate-post-render.py` so Helm's stored manifest includes tracing and a rollout checksum. Future platform upgrades must use that same post-renderer or an equivalent reviewed GitOps patch. An unrelated Helm upgrade without the delta can remove egress export. The helper's additional reconciliation preserves any existing egress policy fields; review manual platform-policy overrides before transferring them into GitOps.

For restricted-egress environments, point these variables to the approved internal OCI charts or imported chart archives before running the installer:

```bash
export FLOW_SUBSTRATE_CHART='{{SUBSTRATE_CHART_ARCHIVE_OR_INTERNAL_OCI_REFERENCE}}'
export FLOW_KAGENT_CHART='{{KAGENT_CHART_ARCHIVE_OR_INTERNAL_OCI_REFERENCE}}'
```

Installed release names are `substrate` and `kagent`. Their namespaces and versions are checked. The chart scripts are intentionally scoped to that reviewed installation contract. Adapt the installer in review if workplace release names differ.

## Use the demo

In existing-agent mode, enter a reviewed prompt for the existing read-only tools. Fixture presets are hidden. In bundled mode, choose the triage, SDLC, identity-isolation, inventory, change-review, or dependency-failure fixture, then select **Send to agent**. The selector fills the prompt; it does not generate telemetry or animate the diagram. In fixture mode the deterministic model calls the named tools and returns a labelled simulated result. Custom fixture prompts default to the inventory workflow unless they contain a supported workflow marker.

The map combines native traces for the current actor by exact identity. Lifecycle buttons open original traces. Token and cost details stay scoped to the selected original trace. Select **Logs** to see API calls and actor state events. The intentionally failed dependency emits an error span while the assistant can still complete its explanation.

Fixture usage is synthetic or omitted, and has no billed model cost. Live mode shows reported token usage. Missing prices remain **Not reported**; the rate controls create explicit estimates and do not establish billed charges. Nested reports for a model call are reconciled through their native parent-span chain.

## Verify the bundled work endpoint

```bash
python3 scripts/verify-https.py \
  --url 'https://{{DEMO_FQDN}}' \
  --context "$KUBE_CONTEXT" \
  --namespace "$FLOW_NAMESPACE" \
  --output '{{PRIVATE_EVIDENCE_DIRECTORY}}/https-verification.json'
```

The verifier validates the server certificate using the system trust store. Add `--ca '{{APPROVED_CA_FILE}}'` for a private CA. It has no certificate-verification bypass. If the approved access layer uses a bearer token, supply it through `FLOW_AUTH_BEARER`, not a command argument or values file.

The check submits actual prompts through HTTPS. It requires model and server-side MCP spans, native worker restore/checkpoint operations, actor state logs, a final suspended actor, all eight component roles, and an exported error for the failure workflow. It also checks that ingress rejects OTLP writes and cross-origin invocation, and that in-cluster Service endpoints are pods rather than host bridges.

The receipt does not mark AKS, Istio runtime behavior, or network-policy enforcement proven automatically. Record the target platform, ingress revision, certificate/access integration, and relevant network-policy tests alongside the work receipt.

## Rehearse HTTPS without Istio

```bash
export KUBE_CONTEXT='{{LOCAL_CLUSTER_CONTEXT}}'
export FLOW_NAMESPACE=agent-flow-demo
export FLOW_TLS_DIR='{{PRIVATE_LOCAL_TLS_DIRECTORY}}'
export FLOW_STATE_DIR='{{PRIVATE_ROLLBACK_DIRECTORY}}'
bash scripts/local-tls.sh
bash scripts/deploy.sh deploy/values/local.yaml
kubectl --context "$KUBE_CONTEXT" -n "$FLOW_NAMESPACE" port-forward --address 127.0.0.1 svc/flow-https 9443:443
```

Open https://localhost:9443. The local certificate is signed by the generated lab CA. Trust that public CA in a dedicated test browser if needed; the scripts do not alter the computer's trust store. The automated test uses `--ca "$FLOW_TLS_DIR/ca.crt"` and verifies TLS normally. This local port-forward is client access to the HTTPS ingress Service. It is not a runtime connection between application components.

The Caddy image needs `NET_BIND_SERVICE` in its capability bounding set because its executable carries that file capability. The local pod still runs as a non-root user with a read-only root filesystem. The AKS profile deploys no Caddy pod.

## Limits and rollback

The dashboard is one replica with bounded in-memory history. A rollout clears history. Component pulses occur when completed spans arrive, not necessarily while work is still in flight. Each prompt creates a new session, so multi-turn restoration of a conversation is not claimed. Original trace IDs remain inspectable. Prompt and tool-result log bodies are discarded.

The Istio profile uses the managed ingress gateway and explicitly leaves demo and sandbox workloads outside sidecar injection. Full mesh interception of Substrate workers is a separate compatibility task. The local kind CNI does not prove enforcement of the included ingress NetworkPolicy.

Follow [ROLLBACK.md](ROLLBACK.md) to restore the previous telemetry destination before uninstalling the demo. Do not delete the platform namespaces, databases, snapshot storage, provider Secrets, or TLS Secret as part of demo cleanup.

Use [DEMO-SCENARIOS.md](DEMO-SCENARIOS.md) for triage and SDLC examples. Use [ENTRA-ISOLATION-DEMO.md](ENTRA-ISOLATION-DEMO.md) for the separate identity allow/deny demonstration and its evidence requirements.
