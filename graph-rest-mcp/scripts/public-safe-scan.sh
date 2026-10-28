#!/usr/bin/env bash
# public-safe-scan.sh — single source of truth for the public-safety scan that
# was previously hand-copied into every work-agent-bundle verify-bundle.sh and
# scripts/verify-kagent-triage-v2-handoff.sh.
#
# Scans a path for private-looking content that must never land in this public
# repo: RFC1918 addresses, private registry hosts, tokens, and passwords
# (see AGENTS.md "Do not add secrets…" and CONTRIBUTING.md).
#
# Usage:
#   scripts/public-safe-scan.sh [PATH] [--allowlist FILE] [--strict] [--json]
#
#   PATH              File or directory to scan (default: current directory)
#   --allowlist FILE  File of glob patterns (one per line, # comments allowed)
#                     to exclude from the scan, e.g. scripts/verify-bundle.sh
#   --strict          Also match bearer/token=/secret:/GUID patterns
#                     (noisier; intended for handover packages)
#   --json            Print {"clean":bool,"hits":N} instead of the hit list
#
# Exit codes: 0 clean; 1 hits found; 2 usage/tooling error.
set -euo pipefail

PATTERN='192\.168\.|10\.[0-9]|172\.(1[6-9]|2[0-9]|3[0-1])\.|redpanda\.redpanda|PRIVATE-TOKEN|password='
STRICT_PATTERN='[Bb]earer |token=|secret:|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

TARGET="."
ALLOWLIST=""
STRICT=0
JSON_OUT=0

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allowlist) ALLOWLIST="$2"; shift 2 ;;
    --strict)    STRICT=1; shift ;;
    --json)      JSON_OUT=1; shift ;;
    -h|--help)   usage 0 ;;
    -*)          echo "public-safe-scan.sh: unknown option: $1" >&2; exit 2 ;;
    *)           TARGET="$1"; shift ;;
  esac
done

[[ -e "$TARGET" ]] || { echo "public-safe-scan.sh: no such path: $TARGET" >&2; exit 2; }
command -v rg >/dev/null 2>&1 || { echo "public-safe-scan.sh: rg (ripgrep) is required" >&2; exit 2; }
if [[ -n "$ALLOWLIST" && ! -f "$ALLOWLIST" ]]; then
  echo "public-safe-scan.sh: allowlist file not found: $ALLOWLIST" >&2
  exit 2
fi

if [[ "$STRICT" -eq 1 ]]; then
  PATTERN="${PATTERN}|${STRICT_PATTERN}"
fi

RG_ARGS=(-n --no-messages --glob '!.git/**')
if [[ -n "$ALLOWLIST" ]]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    RG_ARGS+=(--glob "!$line")
  done < "$ALLOWLIST"
fi

set +e
HITS=$(rg "${RG_ARGS[@]}" "$PATTERN" "$TARGET")
RG_RC=$?
set -e

if [[ "$RG_RC" -gt 1 ]]; then
  echo "public-safe-scan.sh: rg failed (rc=$RG_RC)" >&2
  exit 2
fi

HIT_COUNT=0
[[ -n "$HITS" ]] && HIT_COUNT=$(printf '%s\n' "$HITS" | grep -c .)

if [[ "$JSON_OUT" -eq 1 ]]; then
  if [[ "$HIT_COUNT" -eq 0 ]]; then
    printf '{"clean":true,"hits":0}\n'
  else
    printf '{"clean":false,"hits":%d}\n' "$HIT_COUNT"
  fi
else
  if [[ "$HIT_COUNT" -eq 0 ]]; then
    echo "PUBLIC_SAFE_SCAN_OK: yes"
  else
    printf '%s\n' "$HITS"
    echo "PUBLIC_SAFE_SCAN_FAILED: $HIT_COUNT hit(s)" >&2
  fi
fi

[[ "$HIT_COUNT" -eq 0 ]] && exit 0 || exit 1
