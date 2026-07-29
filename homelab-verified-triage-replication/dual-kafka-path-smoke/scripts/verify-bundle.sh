#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
kubectl kustomize "$ROOT/config" >/dev/null
kubectl kustomize "$ROOT/fixtures" >/dev/null
for script in "$ROOT"/scripts/*.sh; do bash -n "$script"; done
rg -q 'DUAL-KAFKA-SMOKE' "$ROOT/fixtures/dual-kafka-marker.yaml"
rg -q 'apply -k "\$HERE/fixtures"' "$ROOT/scripts/smoke.sh"
if rg -n --glob '!scripts/verify-bundle.sh' 'pkc-|192\.168\.|10\.[0-9]|PRIVATE-TOKEN' .; then
  exit 1
fi
echo "DUAL_KAFKA_PATH_SMOKE_VERIFY: passed"
