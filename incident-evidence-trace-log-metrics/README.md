# Incident Evidence: Trace, Log, Metrics

## TL;DR

Builds a concise incident evidence pack from Grafana MCP metrics, logs,
dashboards, traces when available, and explicit trace fallback when not.

## What This Feature Does

- Discovers Grafana MCP read tools.
- Runs at least one PromQL and one LogQL query.
- Attempts trace lookup where trace context exists.
- Attaches dashboard or panel links.
- Produces a sanitized evidence summary for triage.

## Evidence To Produce

- Grafana MCP tools and datasource names.
- PromQL result.
- LogQL result.
- Trace link or explicit fallback.
- Dashboard/panel link.
- Evidence pack summary.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/incident-evidence-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The evidence pack is source-backed, concise, sanitized, and does not give the
evidence agent mutation permissions.
