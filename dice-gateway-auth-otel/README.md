# DICE gateway authentication and observability

This separate work bundle secures a copy of the ordinary Python agent recorded on 11 November. It keeps the recorded runtime and reviewed skill/knowledge mounts, adds two authenticated Agent Gateway hops, and supplies OTel collection and a Grafana dashboard. Start with [the one-sheet](ONE-SHEET.md).

For the workplace main-Go-Agent walkthrough and adaptive-agent registration discussion, give the work agent [WORK-AGENT-README.md](WORK-AGENT-README.md). It sets the missing evidence gates and links the registration proposal and a short Teams message draft.

The original [DICE lifecycle bundle](https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/dice-agent-lifecycle-demo) and its video remain historical. This bundle does not modify shared agents, MCP servers, gateways, controllers, or their telemetry exports. The secured clone is a distinct deployment in a dedicated namespace. Consumers must use its gateway endpoint. The original recording agent remains in its source namespace.

## Prepare private inputs

The tested compatibility profile is the native Python runtime/controller `0.7.13`, Agent and RemoteMCPServer `kagent.dev/v1alpha2`, standalone agentgateway `v1.7.0`, collector-contrib image `0.146.0`, Tempo `2.9.0`, and Grafana `12.3.2`. Verify the receiving schemas and actual images before adapting it. This is not a platform upgrade installer.

Use an explicit non-production context. Check allocatable resources and actual memory before scheduling. Do not place rehearsal workloads on the control plane. The private settings may select a suitable worker and measured resource requests. Defaults do not establish available capacity.

Set these variables privately. Keep the directory outside every Git checkout. The prepare step reads the model credential into that protected directory because the clone needs its own namespaced Secret.

```sh
export DEMO_CONTEXT='{{APPROVED_HOME_LAB_CONTEXT}}'
export SOURCE_NAMESPACE='{{RECORDED_AGENT_NAMESPACE}}'
export DEMO_NAMESPACE='dice-demo'
export DEMO_PRIVATE='{{NEW_ABSOLUTE_PRIVATE_DIRECTORY_OUTSIDE_GIT}}'
python3 prepare.py --context "$DEMO_CONTEXT" \
  --source-namespace "$SOURCE_NAMESPACE" --namespace "$DEMO_NAMESPACE" \
  --agent dice-lifecycle-recording --api-server-cidr '{{API_ENDPOINT_IP}}/32' \
  --python-image '{{APPROVED_PYTHON_IMAGE_AT_SHA256_DIGEST}}' \
  --private-dir "$DEMO_PRIVATE" --include-model-credential
```

`prepare.py` reads the selected Agent, its approved ModelConfig/credential, mounted ConfigMaps, fixed status record, and public issuer keys. It does not apply anything. Review its private `settings.json` against [settings.example.json](settings.example.json). The model egress selector must match the actual existing model gateway. The API CIDR must identify the actual Kubernetes endpoint after service translation. Copying an arbitrary source Agent is not a review of its permissions or content.

## Render and deploy the home-lab profile

```sh
python3 render.py --settings "$DEMO_PRIVATE/settings.json" \
  --agent "$DEMO_PRIVATE/agent.json" --status "$DEMO_PRIVATE/status.json" \
  --output "$DEMO_PRIVATE/rendered.json"
kubectl --context "$DEMO_CONTEXT" create namespace "$DEMO_NAMESPACE"
kubectl --context "$DEMO_CONTEXT" apply --dry-run=server -f "$DEMO_PRIVATE/rendered.json"
kubectl --context "$DEMO_CONTEXT" apply -f "$DEMO_PRIVATE/prerequisites.json"
kubectl --context "$DEMO_CONTEXT" apply -f "$DEMO_PRIVATE/rendered.json"
```

The render is a Kubernetes List, not a Secret export. Validate the gateway ConfigMap against [the exact upstream v1.7.0 schema](https://github.com/agentgateway/agentgateway/blob/v1.7.0/schema/config.json) as well as Kubernetes server validation. The collector removes span events and retains an allowlist of trace attributes before Tempo export. Native content capture is disabled. Only the fixed MCP producer emits bounded completion metadata to the OTLP logs pipeline.

Prepare the short-lived credentials off screen, without shell tracing. The helper writes private files and the named dedicated MCP Secret, then changes a safe Agent deployment annotation to reconcile the new credential. It makes no agent invocation. Use a fresh credential directory for each renewal.

```sh
python3 credentials.py --context "$DEMO_CONTEXT" --namespace "$DEMO_NAMESPACE" \
  --agent dice-lifecycle-recording --private-dir "$DEMO_PRIVATE/credentials"
```

The controller uses that agent-scoped credential for discovery, and resolves it into the native runtime configuration. Credential expiry fails closed. Verify reconciliation after renewal. The recorded runtime's native file tools can read mounted runtime configuration. This compatibility profile does not isolate credentials from an untrusted model. The token permits only this gateway's synthetic read capability. No OAuth exchange or Entra enforcement is implemented here. `KAGENT_PROPAGATE_TOKEN` and `STS_WELL_KNOWN_URI` remain absent because the recorded runtime treats even the string `false` as enabling propagation.

Wait for all current rollouts, Agent Accepted/Ready, and RemoteMCPServer Accepted. Inspect the effective generated Deployment, ServiceAccounts, policies, and resolved remote URL. The backend MCP identity has only `get` on its named status ConfigMap. A caller and agent identity are not given that backend grant.

The helpers use `Recreate` and config-hash annotations so configuration changes restart the affected process. The native controller normally uses a rolling Deployment. Reserve surge capacity. In a disposable lab with no surge headroom, review a `Recreate` patch for only the generated demo Deployment and record it in the receipt. Do not change a shared controller or other agents to accommodate this rehearsal.

For the lab only, forward **the gateway** to loopback in a separate terminal. Do not forward the controller or agent as the caller path.

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  port-forward svc/dice-agentgateway 28080:8080 28081:8081 --address 127.0.0.1
```

```sh
python3 invoke.py --url http://127.0.0.1:28080/ --allow-loopback-http \
  --token-file "$DEMO_PRIVATE/credentials/caller.token" \
  --receipt-file "$DEMO_PRIVATE/pong.json" \
  --prompt 'Reply with exactly PONG. Do not call tools.' --expect PONG
```

For the combined request, use the recorded bootstrap case and explicitly ask for `aks-known-issues`, both mounted references, and exactly one `get_demo_status` call. Use a new receipt path for every invocation. The helper sends once, follows no redirect, and performs no retry. It prints a requested trace ID; confirm it in received Tempo data before claiming propagation.

## Provision the Grafana view

For a manual Grafana import, upload [grafana-dashboard.json](grafana-dashboard.json) through **Dashboards → New → Import**. Its title is **DICE authenticated agent flow** and its UID is `dice-agent-flow`. This file is a plain dashboard, without Kubernetes ConfigMaps or datasource provisioning. Select your existing Prometheus/Mimir, Tempo, and Loki sources in the dashboard's dropdowns, then set **Demo namespace** to the deployed namespace. Paste a received trace ID to inspect one request.

Importing the dashboard does not configure telemetry collection. The deployed collector must export the `dice_calls_total` and `dice_duration_milliseconds_*` metrics, traces must reach Tempo, and MCP completion logs must carry the expected service labels in Loki. Adapt the queries if the workplace telemetry uses different names. The ConfigMap provisioning alternative remains below.

```sh
python3 dashboard.py --namespace "$DEMO_NAMESPACE" \
  --monitoring-namespace '{{GRAFANA_NAMESPACE}}' \
  --loki-url 'http://{{APPROVED_LOKI_QUERY_SERVICE}}' \
  --output "$DEMO_PRIVATE/dashboard.json"
kubectl --context "$DEMO_CONTEXT" apply --dry-run=server -f "$DEMO_PRIVATE/dashboard.json"
kubectl --context "$DEMO_CONTEXT" apply -f "$DEMO_PRIVATE/dashboard.json"
```

This uses the existing Grafana sidecar labels `grafana_datasource=1` and `grafana_dashboard=1`, and a Prometheus ServiceMonitor selected by `release=kube-prom`. Adapt those labels through the receiving platform's delivery process. It adds dedicated datasource UIDs `dice-tempo` and `dice-loki`, and dashboard UID `dice-agent-flow`. Preserve existing data sources. Confirm datasource health, every panel query, and actual received logs. The lab exporter uses Loki's OTLP endpoint, so it does not depend on the shared Promtail namespace filter.

At work, use existing LGTM exporters, authentication, TLS/CA configuration, telemetry ownership, and approved scrape selection. The lab deploys a disposable single-binary Tempo with `emptyDir` storage and no public Service. It is not a durable production trace store. The dashboard data-source variables permit the existing workplace Tempo, Mimir/Prometheus, and Loki. Resolve its namespace/service selectors and actual metrics before use.

## Verify and roll back

Run `python3 -m unittest discover -s tests -v`, then all live gates in [ONE-SHEET.md](ONE-SHEET.md). Store raw responses and traces privately. `trace_report.py` produces a metadata-only report suitable for review after checking identifiers. Tool execution against synthetic data is not a real AKS investigation. Offline checks are not live evidence.

`probe_auth.py --help` supplies the bounded negative-authentication harness. Prepare valid tokens with the wrong subject and audience through the approved issuer. Each probe sets a fresh trace context and uses an unsupported RPC method, so an unexpected pass does not invoke a model. It requires the expected 401/403 response. Independently compare the MCP loopback audit before/after and inspect received denial traces for absent upstream spans. Run the probes while the demo is idle.

Remove only this profile's Grafana ConfigMaps and dedicated namespace through the approved process. That deletes its cloned credential, synthetic status data, and ephemeral Tempo storage. It leaves source agents, shared model credentials, gateways, and observability services unchanged. Retain any required private receipts before removal. Do not delete a namespace used by another team or reuse this cleanup for the source namespace.
