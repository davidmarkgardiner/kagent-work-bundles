#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in \
  FRONT-SHEET.md \
  CHECKLIST.md \
  GITLAB-TICKETS.md \
  TEAMS-MESSAGES.md \
  GAMEDAY-OPERATING-PLAN.md \
  presentation/kagent-triage-v2-sre-handover.html; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done

for marker in \
  "HANDOVER_PACK_REVIEWED: yes" \
  "GITLAB_TICKET_TEMPLATES_READY: yes" \
  "TEAMS_MESSAGES_READY: yes" \
  "GAMEDAY_PLAN_READY: yes" \
  "HTML_PRESENTATION_READY: yes" \
  "SRE_FEEDBACK_LOOP_DEFINED: yes" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done

for phrase in \
  "Kagent triage v2" \
  "game-day" \
  "feedback loop" \
  "GitLab" \
  "Teams" \
  "SRE"; do
  grep -Rqs "${phrase}" . || { echo "PHRASE_MISSING ${phrase}" >&2; exit 1; }
  echo "PHRASE_OK ${phrase}"
done

if grep -RInE '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS" >&2
  exit 1
fi

echo "TEAM_HANDOVER_PACK_VERIFY: passed"
