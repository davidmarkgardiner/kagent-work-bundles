# GitLab Ticket: Produce AKS Fleet Day-2 Report

## Summary

Create a repeatable AKS fleet reporting workflow for platform and SRE day-to-day
operations.

## Feature

The workflow should collect fleet inventory, health, kagent readiness, incident
funnel data, lifecycle eval scores, and chaos/reliability activity, then return
a sanitized report with follow-up actions.

## Evidence Required

- Cluster/app inventory source.
- Agent readiness summary.
- Incident funnel summary.
- Eval score summary.
- Chaos run summary or not-available marker.
- Report artifact path or URL.

## Acceptance Criteria

- `FLEET_INVENTORY_COLLECTED: yes`
- `AGENT_READINESS_REPORTED: yes`
- `INCIDENT_FUNNEL_REPORTED: yes`
- `EVAL_SCORE_REPORTED: yes`
- `CHAOS_RUNS_REPORTED: yes_or_not_available`
- `REPORT_CREATED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not infer fleet health from one dashboard. List data sources used and gaps.
