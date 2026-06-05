# Prompt: Cert-Manager Observability With Grafana MCP

```text
Use `agents/skills/grafana-incident-evidence-pack/SKILL.md`.

You are running as, or preparing, the cluster-side kagent
`observability-work-agent`. SRE will use kagent UI or A2A/curl. Do not require
SREs to install local MCP servers.

Goal: add cert-manager observability for {{CLUSTER_NAME}} / {{ENVIRONMENT}}.

Use the installed in-cluster Grafana MCP first to inspect existing datasources,
dashboards, alert rules, and live Prometheus/Loki data. Discover the actual
cert-manager metric names and labels before writing queries.

Then produce a durable GitOps change set:
- Alloy scrape/log config if telemetry is missing
- Grafana dashboard JSON for cert-manager health
- alert rules for expiry, renewal failure, ACME/order/challenge failure,
  controller/webhook errors, and missing cert-manager metrics
- alert routing into the kagent triage path, targeting the cert-manager expert
  agent
- kagent UI or A2A request path for SRE
- validation commands and live Grafana MCP proof queries

Open an MR using GitLab MCP if available. Do not commit secrets or internal
hostnames. Use placeholders where needed.

Return:
- kagent UI or A2A/curl access path
- dashboard URL or expected dashboard UID
- alert names and routing labels
- files changed
- MR link
- Grafana MCP queries used as proof
- assumptions or gaps
```
