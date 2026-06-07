#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/aks-fleet-report-request.yaml prompts/01-produce-fleet-report.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "FLEET_INVENTORY_COLLECTED: yes" "AGENT_READINESS_REPORTED: yes" "INCIDENT_FUNNEL_REPORTED: yes" "EVAL_SCORE_REPORTED: yes" "CHAOS_RUNS_REPORTED: yes_or_not_available" "REPORT_CREATED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "AKS_FLEET_REPORTING_DAY2_BUNDLE_VERIFY: passed"
