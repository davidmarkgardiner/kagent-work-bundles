# Grafana MCP Home-Lab Smoke Test

This runbook adds Grafana MCP to the K-Agent / Agent Gateway observability path.
Use it to let agents inspect Grafana dashboards, datasources, Prometheus/Mimir
metrics, Loki logs, and alerting state without giving the agent direct
Kubernetes write permissions.

For the AI observability workflow adapted from the Grafana video transcript, see
[`../ai-grafana/README.md`](../ai-grafana/README.md).

## Why It Helps

Grafana MCP gives the SRE agents a single read path over the LGTM stack:

- list Grafana datasources and dashboard inventory
- inspect dashboard summaries and panel queries
- run PromQL through the configured Prometheus or Mimir datasource
- run LogQL through the configured Loki datasource
- inspect alert rules and routing
- generate Grafana deeplinks for handoff notes

Keep the first rollout read-only. Dashboard writes, alert-rule writes,
annotations, plugin installs, and incident creation should require a separate
approval path and a different service account.

## Install Shape

The preferred home-lab deployment is an in-cluster Grafana MCP server plus a
kagent `RemoteMCPServer`:

```text
kagent Agent
  -> RemoteMCPServer/kagent-grafana-mcp
  -> Service/kagent-grafana-mcp
  -> Grafana API
  -> Prometheus or Mimir, Loki, dashboards, alerting
```

The current upstream-supported install options are Docker for local client use
and Helm for Kubernetes. For this repo, use the Kubernetes shape so kagent and
agentgateway can reach the same MCP endpoint consistently.

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update grafana
helm upgrade --install kagent-grafana-mcp grafana/grafana-mcp \
  --namespace kagent \
  --set grafana.url="http://{{GRAFANA_SERVICE}}.{{GRAFANA_NAMESPACE}}.svc:{{GRAFANA_PORT}}" \
  --set grafana.apiKeySecret.name="grafana-mcp" \
  --set grafana.apiKeySecret.key="GRAFANA_SERVICE_ACCOUNT_TOKEN"
```

If the MCP server is already managed by the kagent chart, do not install a
second copy. Repair the existing ConfigMap or Secret instead.

The official Helm chart uses the `grafana/mcp-grafana` image. Some older or
catalog-driven installs may show `mcp/grafana`; treat the Kubernetes service and
kagent `RemoteMCPServer` as the integration point, and prefer the official chart
for repeatable rebuilds.

## Grafana Token

Create a dedicated Grafana service account. Start with `Viewer` for smoke
testing and only grant write permissions for an explicitly approved write-capable
agent.

Required read-only capabilities for the smoke path:

- `datasources:read`
- `datasources:query`
- `dashboards:read`
- alerting read permissions if alert inspection is required

Store the token in Kubernetes, not in Git:

```bash
kubectl --context {{KUBE_CONTEXT}} -n kagent create secret generic grafana-mcp \
  --from-literal=GRAFANA_SERVICE_ACCOUNT_TOKEN="{{GRAFANA_SERVICE_ACCOUNT_TOKEN}}" \
  --dry-run=client -o yaml | kubectl --context {{KUBE_CONTEXT}} apply -f -
```

Do not pass the token on a Helm command line. Use `grafana.apiKeySecret` so the
Helm release record contains only the Secret name and key, not the token value.

For single-org home-lab Grafana, set the org explicitly:

```bash
kubectl --context {{KUBE_CONTEXT}} -n kagent patch configmap kagent-grafana-mcp \
  --type merge \
  -p '{"data":{"GRAFANA_ORG_ID":"1"}}'
```

Restart the MCP deployment after changing token or org configuration:

```bash
kubectl --context {{KUBE_CONTEXT}} -n kagent rollout restart deploy/kagent-grafana-mcp
kubectl --context {{KUBE_CONTEXT}} -n kagent rollout status deploy/kagent-grafana-mcp
```

## Smoke Test

Run the focused MCP smoke:

```bash
scripts/observability/smoke-grafana-mcp.sh --context {{KUBE_CONTEXT}}
```

Expected proof:

- MCP `initialize` returns server info
- `tools/list` includes `list_datasources` and `query_prometheus`
- `list_datasources` returns Grafana datasource names, types, and UIDs
- `query_prometheus` returns a non-empty result for `count(up)`

Add a Loki check only after the Grafana Loki datasource is healthy:

```bash
scripts/observability/smoke-grafana-mcp.sh \
  --context {{KUBE_CONTEXT}} \
  --loki-datasource-uid loki \
  --loki-query '{namespace="kagent"}'
```

## kagent Wiring

The kagent-facing MCP object should be accepted before agents use it:

```bash
kubectl --context {{KUBE_CONTEXT}} -n kagent get remotemcpserver kagent-grafana-mcp
```

If the work cluster does not already have a `RemoteMCPServer`, create one with a
sanitized manifest:

```yaml
apiVersion: kagent.dev/v1alpha2
kind: RemoteMCPServer
metadata:
  name: kagent-grafana-mcp
  namespace: kagent
spec:
  description: Grafana MCP server
  protocol: STREAMABLE_HTTP
  sseReadTimeout: 5m0s
  terminateOnClose: true
  timeout: 30s
  url: http://kagent-grafana-mcp.kagent:8000/mcp
```

Agents should reference the Grafana MCP server as a `RemoteMCPServer`. Prefer a
read-only tool subset for normal triage agents:

```yaml
tools:
  - type: McpServer
    mcpServer:
      apiGroup: kagent.dev
      kind: RemoteMCPServer
      name: kagent-grafana-mcp
      toolNames:
        - list_datasources
        - search_dashboards
        - get_dashboard_summary
        - get_dashboard_panel_queries
        - query_prometheus
        - query_loki_logs
        - list_prometheus_metric_names
        - list_prometheus_label_names
        - list_prometheus_label_values
        - list_loki_label_names
        - list_loki_label_values
        - alerting_manage_rules
        - alerting_manage_routing
        - generate_deeplink
```

Only include the `alerting_manage_*` tools on a default triage agent when the
Grafana service account is constrained to read-only alert inspection. If the
tool can mutate alert rules or contact point routing in the target Grafana org,
move it to a separate approved workflow.

Keep write-capable tools such as `update_dashboard`, `create_folder`,
`create_annotation`, `install_plugin`, and `create_incident` out of default SRE
triage agents unless a human approval path is in place.

Before applying an agent manifest on a different cluster, compare its configured
`toolNames` with the live MCP discovery result:

```bash
kubectl --context {{KUBE_CONTEXT}} -n kagent get remotemcpserver kagent-grafana-mcp \
  -o jsonpath='{range .status.discoveredTools[*]}{.name}{"\n"}{end}' | sort
```

Remove any stale tool names from the agent manifest before rollout. Current
Grafana MCP releases use tools such as `get_datasource`,
`alerting_manage_rules`, and `alerting_manage_routing`; older examples may
refer to stale names such as `get_datasource_by_uid`, `list_alert_rules`, or
`list_contact_points`.

## Triage Workflow Enrichment

The recommended alert path is:

```text
Grafana Alerting or Alertmanager contact point
  -> Argo Events EventSource
  -> Argo Sensor
  -> Argo Workflow
  -> kagent observability-agent
  -> Grafana MCP
  -> Prometheus/Mimir, Loki, dashboards, alerting metadata
```

Use Alertmanager or Grafana contact points only as the event front door. The
contact point should send the original alert payload into Argo Events, not try
to perform investigation itself. The workflow then asks `observability-agent` to
query Grafana MCP for alert-specific evidence before it returns a verdict.

Good enrichment inputs from the alert payload:

- `labels.alertname` to find related rules and dashboards
- `labels.namespace`, `labels.pod`, `labels.gateway`, and `labels.service` to
  scope PromQL and LogQL queries
- `labels.cluster` to select the right dashboard variable
- `annotations.summary`, `annotations.description`, and `generatorURL` to
  preserve the original alert context

Typical Grafana MCP calls during enrichment:

- `list_datasources` to discover datasource UIDs
- `query_prometheus` for `up`, request rate, error rate, restart, latency, and
  token metrics
- `query_loki_logs` for recent logs in `kagent`, `agentgateway-system`,
  `kgateway-system`, `argo`, and `argo-events`
- `search_dashboards`, `get_dashboard_summary`, and
  `get_dashboard_panel_queries` to find relevant dashboard context
- `generate_deeplink` to return an Explore or dashboard URL in the workflow
  output

This keeps Argo deterministic and auditable: Argo receives the alert, creates a
workflow, and records the transcript. kagent performs the reasoning, while the
Grafana service account controls what observability data it can read.

## Other MCPs To Pair With Grafana

| MCP | Use in this stack | Guardrail |
| --- | --- | --- |
| AKS-MCP | Kubernetes and AKS resource inspection; useful next to Grafana metrics. | Read-only agents should not include apply/delete tools. |
| platform knowledge-base MCP | Ground investigations in runbooks, architecture notes, and known failure modes. | Keep it separate from live execution permissions. |
| memory MCP or native kagent memory | Persist incident patterns and follow-up findings. | Do not mix short A2A session context with durable incident memory. |
| Argo Workflows MCP or OpenAPI shim | Submit approved remediation or evidence workflows. | Agents submit workflows; workflow service accounts hold write permissions. |
| Tempo or trace MCP via Grafana proxied tools | Correlate traces with gateway latency and logs. | Enable only when the Grafana datasource and RBAC scopes are ready. |

## Local Validation Evidence

Validated against a local Kubernetes home-lab context on 2026-05-26.

Observed:

- `RemoteMCPServer/kagent-grafana-mcp` was `ACCEPTED=True`.
- The MCP server was already installed, but its Grafana token returned `401`
  when listing datasources.
- A dedicated Grafana service account token repaired datasource discovery.
- MCP `list_datasources` returned four datasources:
  `Alertmanager`, `Loki`, `Mimir Rule Sync Proof`, and `Prometheus`.
- MCP `query_prometheus` with `count(up)` returned `46`.
- After the worker node recovered, MCP `query_loki_logs` with
  `{namespace="kagent"}` returned recent kagent log lines.
- `observability-agent` was patched to use the current Grafana MCP tool names
  and to keep its default Grafana MCP set read-oriented.
- The Alertmanager-to-Argo triage sensor now calls `observability-agent`, not
  `sre-triage-agent`, so the first AI hop has Grafana MCP access.
- Agent-mediated A2A now reaches the Grafana MCP toolset, but final agent
  responses are blocked while the lab LLM backend is unhealthy. The KubeAI
  `qwen3-14b` pod is failing with an NVIDIA runtime `NVML: Driver/library
  version mismatch`, and the old LiteLLM service referenced by the default model
  config is not present.

Next pickup:

1. Repair the host NVIDIA driver/runtime mismatch or switch
   `observability-agent` to a working non-GPU model route.
2. Re-run the A2A call through `observability-agent`.
3. Run the synthetic alert route once the model backend is healthy.
