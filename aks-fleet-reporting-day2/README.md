# AKS Fleet Reporting Day-2

## TL;DR

Produces a repeatable AKS fleet report for day-to-day platform operations,
covering inventory, health, agent readiness, incidents, eval scores, chaos
runs, and follow-up actions.

## What This Feature Does

- Builds a fleet-level operational view across AKS clusters and applications.
- Summarizes kagent readiness and incident funnel signals.
- Includes lifecycle eval and reliability/game-day status where available.
- Produces a report that SRE/platform can use in regular reviews.

## Evidence To Produce

- Fleet inventory source and scope.
- Agent readiness and incident metrics.
- Eval score summary.
- Chaos/reliability run summary or explicit not-available marker.
- Final report artifact.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/aks-fleet-report-request.yaml`.
4. Capture report evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The report is repeatable, scoped, sanitized, and separates live metrics from
missing or blocked data sources.
