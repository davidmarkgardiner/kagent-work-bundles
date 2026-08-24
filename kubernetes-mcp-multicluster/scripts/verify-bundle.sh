#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO_ROOT=$(cd "$BUNDLE_DIR/../.." && pwd)
CHART_REF=${CHART_REF:-oci://ghcr.io/containers/charts/kubernetes-mcp-server}
CHART_VERSION=${CHART_VERSION:-0.1.0}
IMAGE_VERSION=${IMAGE_VERSION:-latest}
LIVE_VALIDATE=${LIVE_VALIDATE:-0}

for script in "$BUNDLE_DIR"/scripts/*.sh; do
  bash -n "$script"
done

if command -v shellcheck >/dev/null; then
  shellcheck "$BUNDLE_DIR"/scripts/*.sh
fi

python3 - "$BUNDLE_DIR" <<'PY'
import pathlib
import sys
import yaml

for path in pathlib.Path(sys.argv[1]).rglob("*.yaml"):
    with path.open(encoding="utf-8") as stream:
        list(yaml.safe_load_all(stream))
PY

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kubernetes-mcp-chart.XXXXXX")
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

helm pull "$CHART_REF" --version "$CHART_VERSION" --untar --untardir "$tmp_dir" >/dev/null
chart_dir="$tmp_dir/kubernetes-mcp-server"
helm lint "$chart_dir" -f "$BUNDLE_DIR/values.yaml" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.version="$IMAGE_VERSION" >/dev/null
helm template kubernetes-mcp-fleet "$chart_dir" \
  --namespace kubernetes-mcp-poc -f "$BUNDLE_DIR/values.yaml" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.version="$IMAGE_VERSION" >/dev/null

for manifest in "$BUNDLE_DIR"/manifests/*.yaml; do
  kubectl apply --dry-run=client --validate=false -f "$manifest" >/dev/null
done

if test "$LIVE_VALIDATE" = "1"; then
  : "${HOST_CONTEXT:?set HOST_CONTEXT when LIVE_VALIDATE=1}"
  kubectl --context "$HOST_CONTEXT" apply --dry-run=server \
    -f "$BUNDLE_DIR/manifests/agentgateway-kagent.yaml" \
    -f "$BUNDLE_DIR/manifests/kagent-agent.yaml" >/dev/null
fi

"$REPO_ROOT/scripts/public-safe-scan.sh" "$BUNDLE_DIR"
git -C "$REPO_ROOT" diff --check

echo "VERIFY_BUNDLE_OK chart=$CHART_VERSION image=$IMAGE_VERSION live_validate=$LIVE_VALIDATE"
