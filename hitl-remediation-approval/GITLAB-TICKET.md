# GitLab Ticket: Prove HITL Remediation Approval

## Summary

Prove that non-read-only remediation is suspended until a human approval or
denial is recorded.

## Feature

The remediation workflow should propose an action, suspend, capture the
approver and decision, resume only if approved, and verify the outcome.

## Evidence Required

- Remediation proposal.
- Suspended workflow/task.
- Approval/denial record.
- Approver identity or approved placeholder identity.
- Post-approval action proof.
- Verification output.

## Acceptance Criteria

- `REMEDIATION_PROPOSED: yes`
- `WORKFLOW_SUSPENDED: yes`
- `APPROVER_IDENTITY_CAPTURED: yes`
- `APPROVAL_DECISION_RECORDED: yes`
- `REMEDIATION_AFTER_APPROVAL_ONLY: yes`
- `REMEDIATION_VERIFIED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not hardcode "approved" in a demo without showing the suspend/resume or
equivalent approval evidence.
