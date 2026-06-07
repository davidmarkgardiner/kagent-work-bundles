# HITL Remediation Approval Work-Agent Bundle

Purpose: prove non-read-only remediation cannot proceed until a human approval
step records identity, decision, and scope.

## One-Line Ask

Trigger a remediation proposal, suspend before action, record approval or denial,
resume only after approval, and verify the final action and report.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/hitl-remediation-request.yaml`
5. `prompts/01-prove-hitl-remediation.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live Argo, kagent, approval-channel, remediation, or cluster behavior.

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
