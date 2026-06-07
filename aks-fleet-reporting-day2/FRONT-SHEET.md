# AKS Fleet Reporting Day-2 Work-Agent Bundle

Purpose: help platform/SRE teams use Kagent, Grafana, and eval telemetry for
day-to-day AKS fleet operations, reporting, and reliability review.

## One-Line Ask

Produce a repeatable AKS fleet report covering cluster/app inventory, agent
readiness, incidents, eval scores, chaos/reliability runs, and follow-up actions.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/aks-fleet-report-request.yaml`
5. `prompts/01-produce-fleet-report.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live AKS, Grafana, kagent, eval, chaos, or fleet reporting behavior.

## Required Markers

```text
FLEET_INVENTORY_COLLECTED: yes
AGENT_READINESS_REPORTED: yes
INCIDENT_FUNNEL_REPORTED: yes
EVAL_SCORE_REPORTED: yes
CHAOS_RUNS_REPORTED: yes_or_not_available
REPORT_CREATED: yes
OUTPUT_SANITIZED: yes
```
