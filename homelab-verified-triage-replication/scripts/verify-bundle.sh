#!/usr/bin/env bash
# Offline packaging check. Does not contact a cluster or external service.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

for rel in README.md FINDINGS-AND-FIXES.md RUNBOOK.md \
  config/00-namespace.yaml config/01-alloy.yaml config/02-vector.yaml \
  config/03-argo.yaml config/04-workflow-concurrency.yaml config/kustomization.yaml \
  fixtures/confluent-scenarios.yaml fixtures/crashloop-fixture.yaml \
  fixtures/log-fixture.yaml fixtures/retest-fixtures.yaml fixtures/kustomization.yaml \
  fixtures/fixtures/kustomization.yaml fixtures/fixtures/specialist-smoke-fixtures.yaml \
  scripts/deploy.sh scripts/verify.sh scripts/smoke-test.sh scripts/teardown.sh; do
  [[ -f "$rel" ]] || { echo "MISSING $rel" >&2; exit 1; }
done

kubectl kustomize config >/dev/null
kubectl kustomize fixtures >/dev/null
kubectl kustomize fixtures/fixtures >/dev/null
echo "KUSTOMIZE_RENDER_OK"

for script in scripts/*.sh; do
  bash -n "$script"
done
echo "SHELL_SYNTAX_OK"

"$ROOT/scripts/public-safe-scan.sh" . --allowlist scripts/public-safe-scan.allowlist
grep -q 'PRIVATE-TOKEN: \$GITLAB_TOKEN' config/03-argo.yaml
grep -q '{{CONFLUENT_BOOTSTRAP}}' config/03-argo.yaml
grep -q '{{CONFLUENT_TOPIC}}' config/03-argo.yaml
! rg -q 'pkc-[a-z0-9-]+\.[a-z0-9.-]+\.confluent\.cloud|project `[0-9]{5,}`' .
echo "PUBLIC_SAFE_RUNTIME_CONTRACT_OK"

echo "HOMELAB_VERIFIED_TRIAGE_REPLICATION_VERIFY: passed"
