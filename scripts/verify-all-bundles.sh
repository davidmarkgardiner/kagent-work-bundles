#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "== work-agent bundle verifier =="
for bundle in */FRONT-SHEET.md; do
  bundle_dir="$(dirname "${bundle}")"
  for artifact in README.md GITLAB-TICKET.md VISUAL.html; do
    if [[ ! -f "${bundle_dir}/${artifact}" ]]; then
      echo "MISSING ${bundle_dir}/${artifact}" >&2
      exit 1
    fi
    echo "HANDOVER_ARTIFACT_OK ${bundle_dir}/${artifact}"
  done
done

for verifier in */scripts/verify-bundle.sh; do
  echo
  echo "== ${verifier} =="
  bash "${verifier}"
done

echo
echo "WORK_AGENT_BUNDLES_VERIFY: passed"
