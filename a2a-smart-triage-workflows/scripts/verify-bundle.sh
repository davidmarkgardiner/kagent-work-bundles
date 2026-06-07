#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/a2a-smart-triage-request.yaml prompts/01-prove-a2a-fanout.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "A2A_BASELINE_COMPLETED: yes" "SPECIALIST_FANOUT_STARTED: yes" "KUBERNETES_SPECIALIST_COMPLETED: yes" "GRAFANA_SPECIALIST_COMPLETED: yes" "KNOWLEDGE_SPECIALIST_COMPLETED: yes" "GITOPS_SPECIALIST_COMPLETED: yes" "CONTEXT_PRESERVED: yes" "SYNTHESIS_CREATED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "A2A_SMART_TRIAGE_WORKFLOWS_BUNDLE_VERIFY: passed"
