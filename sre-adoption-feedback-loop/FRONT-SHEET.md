# SRE Adoption Feedback Loop Work-Agent Bundle

Purpose: move Kagent triage v2 from engineering proof into SRE day-to-day use by
running a first-contact onboarding flow, capturing SRE feedback, routing
improvements, and reporting whether the workflow is actually being used.

## One-Line Ask

Take one SRE-owned application or namespace, run the first-contact onboarding
and one controlled incident/game-day exercise, prove the agent workflow was used
by SRE, capture feedback, route improvements, and produce an adoption report.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/sre-adoption-request.yaml`
5. `prompts/01-run-sre-first-contact-and-feedback-loop.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

## Required Markers

```text
SRE_OWNER_IDENTIFIED: yes
APPLICATION_SELECTED: yes
FIRST_CONTACT_RUN_COMPLETED: yes
CHAOS_OR_INCIDENT_EXERCISE_COMPLETED: yes
KAGENT_WORKFLOW_USED_BY_SRE: yes
FEEDBACK_CAPTURED: yes
IMPROVEMENT_ITEM_ROUTED: yes
ADOPTION_REPORT_CREATED: yes
DASHBOARD_OR_METRICS_UPDATED: yes_or_not_available
OUTPUT_SANITIZED: yes
```

## Operating Boundary

This bundle is not a replacement for the technical bundles. It is the wrapper
that proves SRE can use them in a real operating loop.

- Run `runtime-model-gateway-readiness/` before scheduling a live SRE exercise,
  so the session does not stall on model, Agent Gateway, A2A, or MCP readiness.
- Use `chaos-reliability-remediation/` for controlled failure injection.
- Use `incident-evidence-trace-log-metrics/` for Grafana evidence packs.
- Use `gitlab-mcp-gitops-pr/` for reviewable code, docs, or runbook changes.
- Use `kagent-triage-v2-kb-gitlab-mcp/` for KB and querydoc improvements.
- Use `lifecycle-evaluation-review-manager/` for scoring and hard gates.
- Use `policy-governance-safety/` when permissions or boundaries are unclear.

Static verification proves the handoff is internally consistent. Live proof
requires an approved work environment and real SRE participation.
