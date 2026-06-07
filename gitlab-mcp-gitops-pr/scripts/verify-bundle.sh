#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/gitlab-gitops-pr-request.yaml prompts/01-create-reviewable-gitops-pr.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md OFFICIAL-GITLAB-MCP-SPIKE-2026-06-07.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "KAGENT_MCP: called" "GITLAB_BRANCH: created" "GITLAB_FILE: created_or_updated" "GITLAB_MR: created" "GITLAB_MR_NOTE: created" "HUMAN_REVIEW_REQUIRED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
for phrase in "MCP_REMOTE_OAUTH_DISCOVERY: passed" "MCP_REMOTE_TOOLS_LIST: failed_404_after_auth" "KAGENT_REMOTEMCPSERVER_ACCEPTED: yes"; do
  grep -q "${phrase}" OFFICIAL-GITLAB-MCP-SPIKE-2026-06-07.md || { echo "SPIKE_PHRASE_MISSING ${phrase}" >&2; exit 1; }
  echo "SPIKE_PHRASE_OK ${phrase}"
done
if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi
echo "GITLAB_MCP_GITOPS_PR_BUNDLE_VERIFY: passed"
