# GitLab Ticket: Prove SRE Grafana MCP Observability Workflow

## Summary

Prove SRE can send an observability request to kagent and receive live Grafana
MCP evidence plus GitOps-reviewed observability changes or blockers.

## Feature

The `observability-work-agent` should accept a payload, use installed Grafana
MCP tools, inspect cert-manager telemetry, and return dashboard, alert, Alloy,
triage-route, and GitLab MR decisions.

## Evidence Required

- Exact payload sent to kagent.
- kagent UI/A2A front door.
- Grafana MCP RemoteMCPServer status and tools.
- Datasource discovery.
- Prometheus/Mimir query result.
- Loki query result.
- Cert-manager metric/log discovery or blocker.
- Dashboard/alert/Alloy/triage decisions.
- GitLab MR status.

## Acceptance Criteria

- `AGENT_PAYLOAD_RECORDED: yes`
- `GRAFANA_MCP_ACCEPTED: yes_or_blocked`
- `GRAFANA_MCP_TOOLS: discovered_or_blocked`
- `GRAFANA_DATASOURCES: discovered_or_blocked`
- `PROMETHEUS_QUERY_EXECUTED: yes_or_blocked`
- `LOKI_QUERY_EXECUTED: yes_or_blocked`
- `REUSABLE_WORKFLOW_PROVEN: yes_or_partial_or_blocked`
- `LIVE_PROOF: yes_or_blocked`

## Notes

Do not accept `scripts/verify-bundle.sh` as live proof. The ticket is complete
only when tool calls or exact blockers are shown.
