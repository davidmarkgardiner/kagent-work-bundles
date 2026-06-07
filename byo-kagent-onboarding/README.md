# Bring Your Own Kagent Onboarding

## TL;DR

Lets an application or platform team onboard their own kagent safely, starting
with read-only triage and optionally adding bounded, approval-gated remediation.

## What This Feature Does

- Captures a team request for a new agent.
- Renders or verifies agent instructions and ToolGrant scope.
- Proves allowed read-only tools work.
- Proves dangerous tools are absent or denied.
- Documents how remediation would be gated.

## Evidence To Produce

- Agent manifest or rendered config.
- ToolGrant scope.
- Read-only triage proof.
- Dangerous-tool denial proof.
- Demo report for the owning team.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/byo-kagent-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The team-owned agent can perform bounded triage, cannot access forbidden tools,
and any remediation path is explicitly scoped and gated.
