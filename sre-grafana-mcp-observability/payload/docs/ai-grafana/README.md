# AI + Grafana Observability Adaptation

This folder adapts a Grafana AI observability demo transcript into this repo's
kagent, agentgateway, Argo Events, and Grafana MCP setup.

The raw transcript is useful as source material, but the portable pattern for
this repo is:

```text
alert or operator question
  -> deterministic workflow entry point
  -> kagent observability-agent
  -> Grafana MCP read tools
  -> Prometheus or Mimir, Loki, dashboards, alerting metadata
  -> evidence summary, deeplinks, and optional remediation plan
```

## What To Borrow

The strongest idea is not "AI draws charts." It is that the agent should inspect
runtime telemetry directly before it explains an incident or proposes a fix.

Useful prompts are investigation prompts:

- why is this pod restarting?
- what changed in the last hour?
- where is this latency coming from?
- are errors isolated to one namespace, gateway, model backend, or node?
- did the alert start before or after a rollout?

Less useful prompts are charting prompts that only restate dashboard work:

- show CPU
- show memory
- list logs

Grafana dashboards are still valuable for handoff and visual inspection. The
agent should use them as evidence and generate deeplinks, but the default triage
path should return a concise diagnosis grounded in metrics, logs, and alert
metadata.

Use two dashboard types:

- agent home dashboards for domain-wide health and fleet blast-radius checks
- incident evidence dashboards for the exact pod, workload, service, cluster,
  logs, metrics, and recovery signal shown to the SRE

Use a shared `grafana-evidence-agent` for Grafana dashboard selection and SRE
evidence packs. Domain agents keep Kubernetes/AKS inspection and pass a
normalized incident payload plus their Kubernetes observations; the evidence
agent returns focused dashboard links, PromQL, LogQL, fleet scope, and
verification queries. This keeps dashboard logic consistent instead of copying
it into every domain agent.

The routing contract is now captured in
[`../../observability/grafana/dashboard-registry.yaml`](../../observability/grafana/dashboard-registry.yaml).
The first reusable incident template is
[`../../observability/grafana/dashboards/k8s-pod-crash-evidence.json`](../../observability/grafana/dashboards/k8s-pod-crash-evidence.json).
For a paste-ready handoff to another implementation agent, use
[`work-agent-implementation-prompt.md`](work-agent-implementation-prompt.md).

## How It Maps To This Stack

| Video concept | This repo's implementation |
| --- | --- |
| Grafana Assistant in the browser | Optional UI assistant. Useful for visual exploration, but not the primary automation path. |
| Claude Code with Grafana MCP | kagent `observability-agent` with a `RemoteMCPServer` pointing at Grafana MCP. |
| Hosted Grafana MCP | Use only for Grafana Cloud. Self-managed labs use the open-source Grafana MCP server in-cluster. |
| Runtime-aware coding agent | kagent plus agentgateway/A2A, with Grafana MCP for telemetry and Argo/GitOps for controlled actions. |
| Dynamic dashboards | Separate write-capable workflow, not part of the default read-only triage agent. |
| Dashboard JSON editing | Treat dashboard JSON as source: fetch clean baseline, make minimal diffs, validate, and review before push. |

In kagent terms, the "Grafana MCP" is not a different MCP implementation. The
kagent side is the `RemoteMCPServer` object and agent `toolNames` wiring. The MCP
server itself should be the official Grafana MCP implementation or the chart
installed equivalent.

## Current Home-Lab State

The direct MCP data path has been validated in the local lab:

- Grafana MCP initializes and lists tools.
- `list_datasources` returns Alertmanager, Loki, Mimir/Prometheus-compatible,
  and Prometheus datasources.
- `query_prometheus` succeeds with `count(up)`.
- `query_loki_logs` succeeds for recent `kagent` and Argo workflow logs.
- `observability-agent` is wired to current Grafana MCP tool names.
- The alert triage sensor calls `observability-agent` so the first AI hop can
  use Grafana MCP evidence.
- The chaos iteration review path completed after the Qwen model pod was
  repaired: Litmus passed, the A2A call returned `QWEN_TRIAGE_STATUS=completed`,
  and the workflow wrote Hive Mind evidence.

If the model backend regresses, use the direct MCP smoke test as proof that
Grafana data access still works, then repair the model route before trusting the
full agent-mediated answer path.

## Triage Pattern

Use Grafana or Alertmanager as the event front door, then let Argo record and
drive the workflow:

```text
Grafana Alerting or Prometheus Alertmanager
  -> Argo Events EventSource
  -> Argo Sensor
  -> Argo Workflow
  -> kagent observability-agent
  -> Grafana MCP
  -> Prometheus/Mimir, Loki, dashboards, alerting metadata
```

The contact point should deliver the original alert payload. It should not do
the investigation itself.

The workflow prompt should ask the agent to:

1. identify the affected labels from the alert payload
2. discover datasource UIDs
3. query metrics for health, errors, restarts, latency, and saturation
4. query recent logs for matching namespace, pod, gateway, or service labels
5. inspect relevant dashboards and panel queries when available
6. return a verdict with evidence, uncertainty, and Grafana deeplinks
7. submit remediation only through an approved Argo/GitOps path

## Tool Policy

Default SRE triage agents should be read-oriented:

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

Add alerting tools only when the Grafana service account is constrained to
read-only alert inspection. If a tool can mutate alert rules or contact point
routing, keep it out of the default triage agent.

Keep these out of default agents unless a human approval path exists:

- `alerting_manage_rules`
- `alerting_manage_routing`
- `update_dashboard`
- `create_folder`
- `create_annotation`
- `install_plugin`
- `create_incident`

The dashboard generation idea is useful, but dashboard writes should be a
separate workflow with a different service account and review gate.

## Chaos And Alert Evidence Loop

The chaos-testing path and Grafana MCP path are implemented as adjacent pieces:

- LitmusChaos can inject bounded faults against `chaos-demo/chaos-target`.
- `chaos/litmus/manifests/sensor-litmus-triage.yaml` routes completed
  `ChaosResult` events into an Argo Workflow that invokes `chaos-triage-agent`.
- `k8s/observability/k-agent-alert-triage-sensor.yaml` routes observability
  alerts into `observability-agent` and asks it to use Grafana MCP evidence.
- `scripts/observability/smoke-grafana-mcp.sh` proves the direct Grafana MCP
  path independently of model backend health.

What is not the default path is letting the triage agent mutate Grafana
dashboards directly. A terminal agent can create a local HTML dashboard for the
human, and a separate approved workflow can publish Grafana dashboard JSON with
a write-capable service account.

Use the new reusable skill for this workflow:

- [Grafana chaos incident triage skill](../../agents/skills/grafana-chaos-incident-triage/SKILL.md)
- [Grafana incident evidence pack skill](../../agents/skills/grafana-incident-evidence-pack/SKILL.md)

For a human-facing map of what is implemented and where to click, open:

- [Agent dashboards and incident evidence packs](agent-dashboard-evidence-pattern.md)
- [Shared Grafana evidence agent](shared-grafana-evidence-agent.md)
- [Chaos + Grafana MCP triage dashboard](chaos-grafana-triage-dashboard.html)
- [Iteration review chaos agent demo](iteration-review-chaos-agent-demo.html)

For the work-cluster proof sequence with Teams HITL, Argo resume, scoped
remediation, and GitLab closeout, use:

- [End-to-end HITL demo runbook](end-to-end-hitl-demo.md)

## Demonstrations

Use the local runbook to demonstrate this pattern end to end:

- [kagent Grafana MCP demo](kagent-grafana-mcp-demo.md)
- [Grafana MCP home-lab smoke test](../observability/grafana-mcp-home-lab.md)
