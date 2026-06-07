# HITL Remediation Approval

## TL;DR

Proves non-read-only remediation cannot proceed until a human approval step
records identity, decision, scope, and outcome.

## What This Feature Does

- Creates a remediation proposal.
- Suspends before the non-read-only action.
- Records approval or denial.
- Resumes only after approval.
- Verifies and reports the final action.

## Evidence To Produce

- Remediation proposal.
- Suspended workflow/task state.
- Approver identity and decision.
- Post-approval action proof.
- Verification and sanitized report.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/hitl-remediation-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The workflow proves the action is blocked before approval, proceeds only after
approval, and records the decision in a durable audit trail.
