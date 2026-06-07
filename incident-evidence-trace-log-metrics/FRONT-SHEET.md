# Incident Evidence Trace Log Metrics Work-Agent Bundle

Purpose: prove an SRE or triage agent can collect a concise, source-backed
incident evidence pack from metrics, logs, traces, dashboards, and known
fallbacks without giving the evidence agent mutation permissions.

## One-Line Ask

Use the installed Grafana MCP and platform evidence-agent pattern to build an
incident evidence pack that correlates PromQL, LogQL, dashboard links, trace
links when available, fallback markers when not available, and a sanitized
summary for the triage coordinator.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/incident-evidence-request.yaml`
5. `prompts/01-build-incident-evidence-pack.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

## Required Markers

```text
GRAFANA_MCP_TOOLS_DISCOVERED: yes
METRICS_QUERY_EXECUTED: yes
LOG_QUERY_EXECUTED: yes
TRACE_LOOKUP_EXECUTED_OR_FALLBACK: yes
DASHBOARD_LINK_ATTACHED: yes
EVIDENCE_PACK_CREATED: yes
TRIAGE_SYNTHESIS_UPDATED: yes
NO_MUTATION_TOOLS_GRANTED: yes
OUTPUT_SANITIZED: yes
```

## Definition Of Done

- Grafana MCP read tools are discovered.
- At least one PromQL query and one LogQL query are executed.
- Trace lookup is attempted if a trace datasource or trace context exists.
- If traces are unavailable, the output includes an explicit fallback marker and
  does not invent trace evidence.
- Dashboard or panel links are attached.
- The final evidence pack is concise enough for an incident report.
- The evidence agent has no Kubernetes mutation, GitLab write, delete, or exec
  tools.
