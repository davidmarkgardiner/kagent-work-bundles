#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/lifecycle-evaluation-request.yaml prompts/01-run-lifecycle-eval.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "EVAL_CASES_LOADED: yes" "PASSING_RUN_SCORED: yes" "BELOW_THRESHOLD_RUN_SCORED: yes" "HARD_FAILURES_ENFORCED: yes" "REVIEW_MANAGER_ROUTED: yes" "METRICS_EXPORTED: yes_or_blocked" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "LIFECYCLE_EVALUATION_REVIEW_MANAGER_BUNDLE_VERIFY: passed"
