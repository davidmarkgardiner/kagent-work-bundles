# HITL Remediation Approval Work-Agent Bundle

Purpose: prove non-read-only remediation cannot proceed until a human approval
step records identity, decision, and scope.

## One-Line Ask

Trigger a remediation proposal, suspend before action, record approval or denial,
resume only after approval, and verify the final action and report.

## Required Markers

```text
REMEDIATION_PROPOSED: yes
WORKFLOW_SUSPENDED: yes
APPROVER_IDENTITY_CAPTURED: yes
APPROVAL_DECISION_RECORDED: yes
REMEDIATION_AFTER_APPROVAL_ONLY: yes
REMEDIATION_VERIFIED: yes
OUTPUT_SANITIZED: yes
```
