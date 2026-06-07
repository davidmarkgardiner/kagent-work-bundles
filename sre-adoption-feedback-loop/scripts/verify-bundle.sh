#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in \
  FRONT-SHEET.md \
  WORK-AGENT-START-PROMPT.md \
  CHECKLIST.md \
  requests/sre-adoption-request.yaml \
  prompts/01-run-sre-first-contact-and-feedback-loop.md \
  payload/REFERENCE.md \
  evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done

for marker in \
  "SRE_OWNER_IDENTIFIED: yes" \
  "APPLICATION_SELECTED: yes" \
  "FIRST_CONTACT_RUN_COMPLETED: yes" \
  "CHAOS_OR_INCIDENT_EXERCISE_COMPLETED: yes" \
  "KAGENT_WORKFLOW_USED_BY_SRE: yes" \
  "FEEDBACK_CAPTURED: yes" \
  "IMPROVEMENT_ITEM_ROUTED: yes" \
  "ADOPTION_REPORT_CREATED: yes" \
  "DASHBOARD_OR_METRICS_UPDATED: yes_or_not_available" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done

for ref in \
  "../chaos-reliability-remediation/" \
  "../incident-evidence-trace-log-metrics/" \
  "../gitlab-mcp-gitops-pr/" \
  "../kagent-triage-v2-kb-gitlab-mcp/" \
  "../lifecycle-evaluation-review-manager/"; do
  grep -Rqs "${ref}" FRONT-SHEET.md payload/REFERENCE.md || {
    echo "REFERENCE_MISSING ${ref}" >&2
    exit 1
  }
  echo "REFERENCE_OK ${ref}"
done

if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi

echo "SRE_ADOPTION_FEEDBACK_LOOP_BUNDLE_VERIFY: passed"
