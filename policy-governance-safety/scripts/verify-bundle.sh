#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in \
  FRONT-SHEET.md \
  WORK-AGENT-START-PROMPT.md \
  CHECKLIST.md \
  requests/policy-governance-request.yaml \
  prompts/01-run-policy-governance-audit.md \
  payload/REFERENCE.md \
  evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done

for marker in \
  "POLICY_BASELINE_COLLECTED: yes" \
  "TOOLGRANTS_AUDITED: yes" \
  "FORBIDDEN_TOOLS_BLOCKED: yes" \
  "PROD_CHAOS_BLOCKED: yes" \
  "GITLAB_WRITE_BOUNDARY_VERIFIED: yes" \
  "MEMORY_WRITE_BOUNDARY_VERIFIED: yes" \
  "SECRET_LEAK_SCAN_PASSED: yes" \
  "POLICY_REPORT_CREATED: yes" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done

for reference in \
  "validate-agent-tool-grants.yaml" \
  "mcp-dangerous-verb.yaml" \
  "validate-chaos-test-safety.yaml" \
  "chaos-test.schema.yaml" \
  "k8s-tool-catalog.yaml"; do
  grep -Rqs "${reference}" payload/REFERENCE.md || { echo "REFERENCE_MISSING ${reference}" >&2; exit 1; }
  echo "REFERENCE_OK ${reference}"
done

if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi

echo "POLICY_GOVERNANCE_SAFETY_BUNDLE_VERIFY: passed"
