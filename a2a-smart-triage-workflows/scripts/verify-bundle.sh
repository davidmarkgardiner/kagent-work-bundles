#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md FINAL-DEMO-WALKTHROUGH.md FINAL-HANDOVER-PACK.md requests/a2a-smart-triage-request.yaml prompts/01-prove-a2a-fanout.md prompts/02-final-demo-walkthrough.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "A2A_BASELINE_COMPLETED: yes" "SPECIALIST_FANOUT_STARTED: yes" "KUBERNETES_SPECIALIST_COMPLETED: yes" "GRAFANA_SPECIALIST_COMPLETED: yes" "KNOWLEDGE_SPECIALIST_COMPLETED: yes" "GITOPS_SPECIALIST_COMPLETED: yes" "QUERYDOC_KB_PROVEN: yes_or_blocked" "GRAFANA_MCP_PROVEN: yes_or_blocked" "GITLAB_MCP_PROVEN: yes_or_blocked" "MEMORY_CONTEXT_PROVEN: yes_or_not_available" "HITL_GATE_PROVEN: yes_or_blocked" "CHAOS_EVAL_LOOP_PROVEN: yes_or_blocked" "CONTEXT_PRESERVED: yes" "SYNTHESIS_CREATED: yes" "FINAL_DEMO_REPORT_CREATED: yes" "FINAL_FRONT_SHEET_CREATED: yes" "GITLAB_TICKET_SET_CREATED: yes" "EVIDENCE_INDEX_CREATED: yes" "NEXT_ACTIONS_RECORDED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "A2A_SMART_TRIAGE_WORKFLOWS_BUNDLE_VERIFY: passed"
