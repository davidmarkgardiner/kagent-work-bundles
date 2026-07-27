#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
kubectl kustomize "$ROOT/config" >/dev/null
for script in "$ROOT"/scripts/*.sh; do bash -n "$script"; done
if rg -n --glob '!scripts/verify-bundle.sh' 'pkc-|192\.168\.|10\.[0-9]|PRIVATE-TOKEN' .; then
  exit 1
fi
echo "DUAL_KAFKA_PATH_SMOKE_VERIFY: passed"
