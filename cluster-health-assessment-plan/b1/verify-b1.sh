#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../../.." && pwd)"
CONTEXT="${1:-}"

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$ROOT_DIR" -p 'test_*.py' -v
kubectl kustomize "$ROOT_DIR" >/tmp/cluster-health-b1-rendered.yaml

if rg -n 'KAFKA|GITLAB|GITHUB|AGENT_URL|WEBHOOK_URL|secretKeyRef' \
  "$ROOT_DIR/collector.py" "$ROOT_DIR/health.py" "$ROOT_DIR/metrics.py" \
  "$ROOT_DIR/k8s"; then
  echo "unexpected downstream or secret integration found" >&2
  exit 1
fi

if [[ -n "$CONTEXT" ]]; then
  kubectl --context "$CONTEXT" apply --dry-run=server -f /tmp/cluster-health-b1-rendered.yaml >/dev/null
  SA="system:serviceaccount:cluster-health-system:cluster-health-assessor"
  [[ "$(kubectl --context "$CONTEXT" auth can-i --as="$SA" get secrets -n kagent)" == "no" ]]
  [[ "$(kubectl --context "$CONTEXT" auth can-i --as="$SA" create pods -n kagent)" == "no" ]]
  [[ "$(kubectl --context "$CONTEXT" auth can-i --as="$SA" list pods -n default)" == "no" ]]
  [[ "$(kubectl --context "$CONTEXT" auth can-i --as="$SA" list pods -n kagent)" == "yes" ]]
fi

"$REPO_ROOT/scripts/public-safe-scan.sh" "$ROOT_DIR/.." \
  --allowlist "$ROOT_DIR/../public-safe-scan.allowlist" --strict >/dev/null

echo "B1 static and policy verification passed"
