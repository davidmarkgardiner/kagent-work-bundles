#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in \
  FRONT-SHEET.md \
  WORK-AGENT-START-PROMPT.md \
  CHECKLIST.md \
  requests/runtime-readiness-request.yaml \
  prompts/01-run-runtime-model-gateway-preflight.md \
  payload/REFERENCE.md \
  evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done

for marker in \
  "RUNTIME_PREFLIGHT_STARTED: yes" \
  "KAGENT_AGENTS_READY: yes_or_blocked" \
  "MODEL_CONFIG_ACCEPTED: yes" \
  "MODEL_BACKEND_READY: yes_or_blocked" \
  "AGENTGATEWAY_ROUTE_READY: yes_or_blocked" \
  "A2A_SMOKE_COMPLETED: yes_or_blocked" \
  "GRAFANA_MCP_ACCEPTED: yes" \
  "GITLAB_MCP_ACCEPTED_OR_LITE_FALLBACK: yes_or_blocked" \
  "MEMORY_MCP_ACCEPTED: yes_or_not_required" \
  "READINESS_BLOCKERS_RECORDED: yes" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done

for phrase in \
  "ModelConfig Accepted=True" \
  "A2A message/send" \
  "RemoteMCPServer" \
  "Agent Gateway" \
  "Do not mutate"; do
  grep -Rqs "${phrase}" . || { echo "PHRASE_MISSING ${phrase}" >&2; exit 1; }
  echo "PHRASE_OK ${phrase}"
done

if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi

echo "RUNTIME_MODEL_GATEWAY_READINESS_BUNDLE_VERIFY: passed"
