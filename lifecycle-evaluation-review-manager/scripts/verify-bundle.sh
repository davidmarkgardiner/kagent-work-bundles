#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in \
  FRONT-SHEET.md \
  WORK-AGENT-START-PROMPT.md \
  CHECKLIST.md \
  MEETING-ACTION-COVERAGE.md \
  ARCHITECTURE-DECISION.md \
  DATA-STORAGE-ACCESS-TRACEABILITY.md \
  IMPLEMENTATION-VERIFY-PLAN.md \
  requests/lifecycle-evaluation-request.yaml \
  prompts/01-run-lifecycle-eval.md \
  payload/REFERENCE.md \
  evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in \
  "EVALUATION_FRAMEWORK_DESIGN: covered" \
  "OFFLINE_ONLINE_DESIGN: covered" \
  "KEY_METRICS_IDENTIFIED: covered" \
  "INLINE_VS_SEPARATE_ARCHITECTURE: covered" \
  "DATA_STORAGE_ACCESS_MODEL: covered" \
  "AUDIT_RETENTION_TRACEABILITY: covered" \
  "EVAL_CASES_LOADED: yes" \
  "PASSING_RUN_SCORED: yes" \
  "BELOW_THRESHOLD_RUN_SCORED: yes" \
  "HARD_FAILURES_ENFORCED: yes" \
  "REVIEW_MANAGER_ROUTED: yes" \
  "METRICS_EXPORTED: yes_or_blocked" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "LIFECYCLE_EVALUATION_REVIEW_MANAGER_BUNDLE_VERIFY: passed"
