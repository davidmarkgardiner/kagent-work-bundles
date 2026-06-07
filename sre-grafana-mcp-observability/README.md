# SRE Grafana MCP Observability

## TL;DR

Lets SRE send an observability request to a kagent front door. The agent uses
installed Grafana MCP tools to inspect live telemetry, then proposes or creates
GitOps-reviewed Alloy, dashboard, alert, and triage-route changes.

## What This Feature Does

- Receives an SRE payload through kagent UI or A2A.
- Discovers Grafana MCP tools and datasources.
- Runs live Prometheus/Mimir and Loki queries.
- Checks dashboards and alert rules.
- Decides whether to create or update observability config.
- Opens a GitLab MR if approved GitLab tooling is available.

## Evidence To Produce

- Exact payload sent to the agent.
- Agent/front-door used.
- Grafana MCP server status and tools.
- Datasource, PromQL, and LogQL evidence.
- Dashboard, alert, Alloy, and triage-route decisions.
- GitLab MR status.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `prompts/03-live-agent-payload-and-grafana-mcp-proof.md` for live proof.
3. Use `requests/cert-manager-observability-request.json` as the manual test.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The workflow is proven only when payload in, Grafana MCP tool calls, live query
results, decisions, and MR/blocker status are all returned.
