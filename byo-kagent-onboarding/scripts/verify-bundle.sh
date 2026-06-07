#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/byo-kagent-request.yaml prompts/01-onboard-readonly-team-agent.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "BYO_REQUEST_ACCEPTED: yes" "AGENT_RENDERED: yes" "TOOLGRANT_SCOPED: yes" "READ_ONLY_TRIAGE_PROVEN: yes" "DANGEROUS_TOOLS_ABSENT: yes" "POLICY_DENIAL_TESTED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "BYO_KAGENT_ONBOARDING_BUNDLE_VERIFY: passed"
