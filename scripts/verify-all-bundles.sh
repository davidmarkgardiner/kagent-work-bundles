#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "== work-agent bundle verifier =="
for verifier in */scripts/verify-bundle.sh; do
  echo
  echo "== ${verifier} =="
  bash "${verifier}"
done

echo
echo "WORK_AGENT_BUNDLES_VERIFY: passed"
