# GitLab Ticket: Agentic Triage Smoke Tests For New Server

## Summary

Validate the new agentic triage installation with Grafana-origin smoke tests
before routing real alert traffic.

## Objective

Prove that metrics, logs, Kubernetes events, and traces or trace fallback flow
from Grafana/Alertmanager into smart triage, produce source-backed agent output,
score cleanly, and surface success or failure on the Grafana fleet dashboard.

## Scope

- Run runtime readiness for agentgateway, model route, kagent A2A, and fleet
  dashboard metrics.
- Run the smoke matrix in
  `work-agent-bundles/agentic-triage-smoke-tests/SMOKE-RUNBOOK.md`.
- Use whiskey app, `podinfo`, or another approved non-production workload.
- Capture evidence in
  `work-agent-bundles/agentic-triage-smoke-tests/evidence/EVIDENCE-TEMPLATE.md`.
- Run one negative low-score or hard-failure case and verify it alerts.

## Acceptance Criteria

- Direct agentgateway/model smoke passes.
- Single A2A completion passes.
- At least one alert-triggered smart-triage workflow completes.
- Metrics, logs, events, and traces or explicit trace fallback are covered.
- Lifecycle eval score is at least `0.85` with zero hard failures for passing
  smoke runs.
- Grafana dashboard shows agent readiness, incident funnel movement, latest
  score out of 10, and any hard failure.
- No production workload is mutated.

## Safety

Use only non-production targets and test-only routes/contact points. Keep
remediation dry-run until HITL or GitOps approval is explicitly proven.
