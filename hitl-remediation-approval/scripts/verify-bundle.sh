#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/hitl-remediation-request.yaml prompts/01-prove-hitl-remediation.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "REMEDIATION_PROPOSED: yes" "WORKFLOW_SUSPENDED: yes" "APPROVER_IDENTITY_CAPTURED: yes" "APPROVAL_DECISION_RECORDED: yes" "REMEDIATION_AFTER_APPROVAL_ONLY: yes" "REMEDIATION_VERIFIED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "HITL_REMEDIATION_APPROVAL_BUNDLE_VERIFY: passed"
