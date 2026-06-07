#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for rel in FRONT-SHEET.md WORK-AGENT-START-PROMPT.md CHECKLIST.md requests/memory-shared-context-request.yaml prompts/01-prove-memory-shared-context.md payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in "MEMORY_MCP_AVAILABLE: yes" "MEMORY_SEEDED: yes" "MEMORY_RECALLED: yes" "MEMORY_USED_IN_TRIAGE: yes" "CURATOR_PATH_DEFINED: yes" "DANGEROUS_MEMORY_WRITE_BLOCKED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done
echo "MEMORY_MCP_SHARED_CONTEXT_BUNDLE_VERIFY: passed"
