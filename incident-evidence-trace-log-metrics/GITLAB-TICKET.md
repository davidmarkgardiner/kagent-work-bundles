# GitLab Ticket: Build Incident Evidence Pack

## Summary

Prove an incident evidence agent can collect metrics, logs, dashboards, and
trace or fallback evidence through Grafana MCP.

## Feature

The evidence workflow should gather focused Grafana-backed proof for an
incident and return a summary suitable for a triage report or ticket update.

## Evidence Required

- Grafana MCP tool list.
- Datasource discovery.
- PromQL query and result summary.
- LogQL query and result summary.
- Trace lookup or fallback marker.
- Dashboard/panel link.
- Evidence pack.

## Acceptance Criteria

- `GRAFANA_MCP_TOOLS_DISCOVERED: yes`
- `METRICS_QUERY_EXECUTED: yes`
- `LOG_QUERY_EXECUTED: yes`
- `TRACE_LOOKUP_EXECUTED_OR_FALLBACK: yes`
- `DASHBOARD_LINK_ATTACHED: yes`
- `EVIDENCE_PACK_CREATED: yes`
- `TRIAGE_SYNTHESIS_UPDATED: yes`
- `NO_MUTATION_TOOLS_GRANTED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not invent traces. If no trace datasource or trace context exists, return an
explicit fallback marker.
