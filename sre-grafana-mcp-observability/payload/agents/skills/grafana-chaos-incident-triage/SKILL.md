---
name: grafana-chaos-incident-triage
description: Use Grafana MCP, LitmusChaos, Alertmanager, Argo Workflows, and kagent to investigate chaos or production alerts, gather evidence, and produce an SRE-ready visual handoff.
---

# Grafana Chaos Incident Triage

Use this skill when an alert, LitmusChaos result, or operator question needs a
runtime-grounded incident explanation from Grafana telemetry. The default mode is
read-only investigation. Remediation and dashboard writes require an explicit
approval path and a separate write-capable service account.

## Operating Model

The expected stack path is:

```text
LitmusChaos or Grafana/Alertmanager alert
  -> Argo Events
  -> Argo Workflow
  -> kagent observability-agent or chaos-triage-agent
  -> Grafana MCP read tools
  -> Prometheus or Mimir, Loki, dashboards, alert metadata
  -> evidence pack, deeplinks, and SRE handoff
```

Use `chaos-triage-agent` for controlled chaos experiments in `chaos-demo`.
Use `observability-agent` when the alert already came through the K-Agent /
Agent Gateway observability path or when Grafana MCP evidence is the primary
input.

## First Checks

1. Confirm the event source:
   - Litmus: `ChaosResult` name, namespace, experiment, engine, verdict, phase.
   - Alert: alertname, status, severity, cluster, namespace, pod, service,
     gateway, generator URL, startsAt.
2. Confirm the direct Grafana MCP path before trusting agent-mediated output:

```bash
scripts/observability/smoke-grafana-mcp.sh --context {{KUBE_CONTEXT}}
```

3. If the direct smoke fails, classify it before continuing:
   - `401 Unauthorized`: repair Grafana service account token or org ID.
   - `502` on Loki or datasource query: check datasource backend health.
   - Missing tool names: compare the Agent `toolNames` with
     `RemoteMCPServer.status.discoveredTools`.
4. Check whether the model backend is healthy. If the model route is down but
   Grafana MCP works directly, return a direct evidence report and mark
   agent-mediated reasoning as pending.

## Grafana MCP Tool Policy

Use these read tools first:

- `list_datasources`
- `get_datasource`
- `search_dashboards`
- `get_dashboard_summary`
- `get_dashboard_panel_queries`
- `query_prometheus`
- `query_loki_logs`
- `list_prometheus_metric_names`
- `list_prometheus_label_names`
- `list_prometheus_label_values`
- `list_loki_label_names`
- `list_loki_label_values`
- `generate_deeplink`

Use Grafana Assistant through an Ask Assistant tool when available and useful for
Grafana-specific interpretation, query drafting, or dashboard design. Treat its
answer as specialist advice, then verify the underlying metrics and logs through
Grafana MCP before presenting the incident verdict.

Do not use these tools in the default triage path unless the workflow has human
approval and a write-scoped service account:

- `update_dashboard`
- `create_folder`
- `create_annotation`
- `install_plugin`
- `create_incident`
- alert routing or alert rule mutation tools

## Investigation Flow

### 1. Scope The Blast Radius

Start with labels from the alert or chaos event. Always preserve the original
payload in the evidence pack.

Look for:

- affected namespace, workload, pod, node, service, gateway, model, route
- whether the symptom is isolated or cluster-wide
- whether it started after a rollout, chaos injection, node event, or model
  backend change
- whether observability itself is degraded

### 2. Query Metrics

Pick the datasource UID from `list_datasources`, then run bounded queries over
the incident window. Prefer short windows around the alert, then widen if needed.

Common PromQL patterns:

```promql
up{namespace="{{NAMESPACE}}"}
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="{{NAMESPACE}}"}[5m]))
sum by (pod) (container_memory_working_set_bytes{namespace="{{NAMESPACE}}"})
sum by (pod) (increase(kube_pod_container_status_restarts_total{namespace="{{NAMESPACE}}"}[30m]))
sum by (pod) (kube_pod_status_phase{namespace="{{NAMESPACE}}",phase=~"Pending|Failed|Unknown"})
sum by (status_code) (rate(agentgateway_http_requests_total{namespace="{{NAMESPACE}}"}[5m]))
histogram_quantile(0.95, sum by (le, route) (rate(agentgateway_request_duration_seconds_bucket[5m])))
```

For chaos runs, also inspect the controlled target:

```promql
sum by (pod) (up{namespace="chaos-demo"})
sum by (pod) (increase(kube_pod_container_status_restarts_total{namespace="chaos-demo"}[30m]))
```

### 3. Query Logs

Use narrow LogQL first:

```logql
{namespace="{{NAMESPACE}}"} |= "{{WORKLOAD}}"
{namespace="{{NAMESPACE}}"} |~ "error|fail|timeout|panic|denied|unavailable"
{namespace="kagent"} |~ "tool|mcp|error|timeout|model|a2a"
{namespace="agentgateway-system"} |~ "5..|timeout|upstream|backend|denied"
{namespace="argo"} |~ "{{WORKFLOW_NAME}}|Error|Failed"
{namespace="argo-events"} |~ "sensor|eventsource|Failed|Error"
```

For Litmus:

```logql
{namespace="chaos-demo"} |~ "chaos-target|pod-delete|pod-cpu-hog|error|fail"
{namespace="litmus"} |~ "ChaosResult|ChaosEngine|error|fail"
```

### 4. Inspect Dashboards And Alert Context

Use `search_dashboards`, `get_dashboard_summary`, and
`get_dashboard_panel_queries` to find the existing panels closest to the
incident. Do not assume a dashboard is authoritative if its query scope does not
match the alert labels.

Return deeplinks for:

- dashboard overview with variables set where possible
- Explore metric query
- Explore log query
- related alert rule or panel query

### 5. Decide And Present

Classify exactly one outcome:

- `observe_only`: telemetry confirms the fault was contained or expected.
- `human_review`: diagnosis is likely but action is unsafe, ambiguous, or outside
  the bounded namespace.
- `safe_auto_remediate`: only for approved workflows with bounded permissions.

Never modify resources outside the workflow guardrail. For this repo's chaos
demo, the bounded target is `chaos-demo/chaos-target`.

## Evidence Pack Contract

Every answer must include:

- `Incident`: alert or chaos result, status, time window, affected labels.
- `Verdict`: one concise root-cause statement with confidence.
- `Evidence`: metrics, logs, dashboard panels, alert metadata, workflow state.
- `Queries`: exact PromQL and LogQL used, including datasource UID if known.
- `Visuals`: Grafana dashboard or Explore deeplinks; include generated local
  HTML dashboard path when created by the terminal agent.
- `Blast Radius`: affected namespaces, workloads, users, routes, model backends.
- `Uncertainty`: missing telemetry, unhealthy datasources, model backend gaps.
- `Decision`: observe_only, human_review, or safe_auto_remediate.
- `Next Actions`: SRE-ready commands or GitOps/Argo workflow handoff.

When working directly with a human in the terminal, also create or update a
small HTML dashboard under `docs/ai-grafana/` or `tmp/incident-dashboards/` that
shows the incident timeline, evidence, Grafana deeplinks, and decision. Return a
clickable file link to that page.

For work-cluster handoff, use `docs/ai-grafana/end-to-end-hitl-demo.md` as the
proof sequence. It defines the alert, Grafana MCP evidence, Teams HITL, Argo
resume, scoped remediation, verification, and GitLab closeout contract.

## Dashboard Generation Rules

Dynamic Grafana dashboard writes are separate from triage:

1. Fetch or generate dashboard JSON into `tmp/grafana-dashboards/`.
2. Validate with `jq -e .`.
3. Keep diffs minimal and reviewable.
4. Push through a write-capable Grafana MCP account only after approval.
5. Record the resulting dashboard UID and deeplink in the evidence pack.

For a human-facing local dashboard, prefer static HTML that can be opened from
the repo without a server. Include only sanitized placeholders and links to repo
runbooks, manifests, Grafana deeplinks, or command snippets.

## Escalation Rules

Escalate to SRE or HITL when:

- the namespace is not approved for automation
- Grafana MCP cannot query required evidence
- Loki, Mimir, or Grafana itself is unhealthy
- the model backend is unhealthy and the workflow depends on agent reasoning
- the action would change production resources, alert routing, dashboard writes,
  secrets, RBAC, nodes, PVCs, or CRDs
- the root cause is uncertain after two independent telemetry checks

Keep GitLab or the approved issue tracker as the durable audit record. Use chat
or Teams only for time-sensitive human approval.
