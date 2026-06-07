#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in \
  FRONT-SHEET.md \
  WORK-AGENT-START-PROMPT.md \
  CHECKLIST.md \
  requests/incident-evidence-request.yaml \
  prompts/01-build-incident-evidence-pack.md \
  payload/REFERENCE.md \
  evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done

for marker in \
  "GRAFANA_MCP_TOOLS_DISCOVERED: yes" \
  "METRICS_QUERY_EXECUTED: yes" \
  "LOG_QUERY_EXECUTED: yes" \
  "TRACE_LOOKUP_EXECUTED_OR_FALLBACK: yes" \
  "DASHBOARD_LINK_ATTACHED: yes" \
  "EVIDENCE_PACK_CREATED: yes" \
  "TRIAGE_SYNTHESIS_UPDATED: yes" \
  "NO_MUTATION_TOOLS_GRANTED: yes" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done

for reference in \
  "grafana-incident-evidence-pack/SKILL.md" \
  "shared-grafana-evidence-agent.md" \
  "prove-trace-link.sh" \
  "agent.yaml"; do
  grep -Rqs "${reference}" payload/REFERENCE.md || { echo "REFERENCE_MISSING ${reference}" >&2; exit 1; }
  echo "REFERENCE_OK ${reference}"
done

if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi

echo "INCIDENT_EVIDENCE_TRACE_LOG_METRICS_BUNDLE_VERIFY: passed"
