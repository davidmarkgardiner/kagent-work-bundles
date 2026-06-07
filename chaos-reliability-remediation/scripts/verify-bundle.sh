#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/chaos-reliability-request.yaml prompts/01-run-controlled-chaos-demo.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "CHAOS_REQUEST_ACCEPTED: yes" "TARGET_NON_PROD: yes" "CHAOS_INJECTED: yes" "TRIAGE_STARTED: yes" "GRAFANA_EVIDENCE_ATTACHED: yes" "HITL_REQUIRED_FOR_REMEDIATION: yes" "RECOVERY_VERIFIED: yes" "LIFECYCLE_EVAL_RECORDED: yes" "REPORT_CREATED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi
echo "CHAOS_RELIABILITY_REMEDIATION_BUNDLE_VERIFY: passed"
