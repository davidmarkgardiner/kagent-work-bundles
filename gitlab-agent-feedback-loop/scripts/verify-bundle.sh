#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in \
  README.md FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md GITLAB-TICKET.md \
  GITLAB-CONFIGURATION-SHEET.md \
  requests/gitlab-agent-feedback-request.yaml payload/REFERENCE.md \
  prompts/01-private-gitlab-feedback-loop.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "$rel" ]] || { echo "MISSING $rel" >&2; exit 1; }
done

for marker in \
  PRIVATE_ROUTE_REACHABLE TLS_TRUST_CONFIRMED WEBHOOK_AUTH_CONFIRMED \
  ALLOWLIST_AND_LABEL_GATES_CONFIRMED DEDUPLICATION_CONFIRMED \
  READ_ONLY_AGENT_CONFIRMED GITLAB_REPLY_CONFIRMED NO_GITOPS_ACTION_EXECUTED \
  EVIDENCE_CAPTURED OUTPUT_SANITIZED; do
  grep -Rqs "${marker}: yes" . || { echo "MARKER_MISSING $marker" >&2; exit 1; }
done

for ref in \
  '../gitlab-mcp-gitops-pr/' '../hitl-remediation-approval/' \
  '../policy-governance-safety/' '../runtime-model-gateway-readiness/'; do
  grep -Rqs "$ref" payload/REFERENCE.md || { echo "REFERENCE_MISSING $ref" >&2; exit 1; }
done

if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]{12,}|token=|password:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo 'PUBLIC_SAFETY_HITS' >&2
  exit 1
fi

echo 'GITLAB_AGENT_FEEDBACK_LOOP_BUNDLE_VERIFY: passed'
