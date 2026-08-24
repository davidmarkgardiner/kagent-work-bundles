#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$BUNDLE_DIR/../.." && pwd)"

required=(
  README.md
  GITLAB-TICKET.md
  VISUAL.html
  aks-mcp-values.yaml
  manifests/00-core.yaml
  manifests/01-cronworkflow.yaml
  manifests/02-agent.yaml
  manifests/03-argo-agent-router.yaml
  kustomization.yaml
  scripts/refresh-fleet-kubeconfig.sh
  scripts/homelab-smoke.sh
  tests/test-refresh-script.sh
)
for file_name in "${required[@]}"; do
  [[ -s "$BUNDLE_DIR/$file_name" ]] || { echo "missing required file: $file_name" >&2; exit 1; }
done

bash -n "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
bash -n "$BUNDLE_DIR/scripts/homelab-smoke.sh"
bash -n "$BUNDLE_DIR/tests/test-refresh-script.sh"
"$BUNDLE_DIR/tests/test-refresh-script.sh"
kubectl kustomize "$BUNDLE_DIR" >/dev/null
helm lint "$REPO_ROOT/platform/aks-mcp/chart" -f "$BUNDLE_DIR/aks-mcp-values.yaml" >/dev/null
helm template aks-mcp "$REPO_ROOT/platform/aks-mcp/chart" \
  --namespace aks-mcp -f "$BUNDLE_DIR/aks-mcp-values.yaml" \
  | grep -q -- '--allowed-host'
"$REPO_ROOT/scripts/public-safe-scan.sh" "$BUNDLE_DIR"

grep -q 'concurrencyPolicy: Forbid' "$BUNDLE_DIR/manifests/01-cronworkflow.yaml"
grep -q 'BLOCKED_UNKNOWN_CLUSTER' "$BUNDLE_DIR/manifests/03-argo-agent-router.yaml"
grep -q -- '--context, --kubeconfig' "$BUNDLE_DIR/manifests/02-agent.yaml"
grep -q 'SHARD_DIR' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'replace -f' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'UNCHANGED' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"

echo "PASS aks-mcp-fleet-kubeconfig-refresh bundle"
