#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO_ROOT=$(cd "$BUNDLE_DIR/../.." && pwd)
LIVE_VALIDATE=${LIVE_VALIDATE:-0}

# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"
test -f "$CHART_REF/Chart.yaml" || {
  echo "local Helm chart not found: $CHART_REF/Chart.yaml" >&2
  exit 1
}
case "$IMAGE_REGISTRY" in
  quay.io|ghcr.io|docker.io|registry-1.docker.io)
    test "$ALLOW_PUBLIC_IMAGE_FOR_TEST" = "1" || {
      echo "refusing public image registry in air-gapped mode: $IMAGE_REGISTRY" >&2
      exit 1
    }
    ;;
esac
actual_chart_version=$(helm show chart "$CHART_REF" | awk '$1 == "version:" {print $2; exit}')
test "$actual_chart_version" = "$CHART_VERSION" || {
  echo "chart version mismatch: expected=$CHART_VERSION actual=$actual_chart_version" >&2
  exit 1
}

for script in "$BUNDLE_DIR"/scripts/*.sh; do
  bash -n "$script"
done

if command -v shellcheck >/dev/null; then
  shellcheck -x -P "$BUNDLE_DIR/scripts" "$BUNDLE_DIR"/scripts/*.sh
fi

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kubernetes-mcp-chart.XXXXXX")
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

python3 - "$BUNDLE_DIR" <<'PY'
import pathlib
import sys
import yaml

bundle_dir = pathlib.Path(sys.argv[1])

for path in bundle_dir.rglob("*.yaml"):
    with path.open(encoding="utf-8") as stream:
        list(yaml.safe_load_all(stream))
PY

kubectl kustomize "$BUNDLE_DIR" >"$tmp_dir/kustomize-rendered.yaml"
python3 - "$tmp_dir/kustomize-rendered.yaml" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as stream:
    list(yaml.safe_load_all(stream))
PY

chart_dir=$CHART_REF
helm lint "$chart_dir" -f "$BUNDLE_DIR/values.yaml" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" >/dev/null
helm template kubernetes-mcp-fleet "$chart_dir" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" >"$tmp_dir/helm-rendered.yaml"

expected_image="$IMAGE_REGISTRY/$IMAGE_REPOSITORY:$IMAGE_VERSION"
python3 - "$tmp_dir/helm-rendered.yaml" "$expected_image" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as stream:
    documents = list(yaml.safe_load_all(stream))
images = [
    container["image"]
    for document in documents
    if document and document.get("kind") == "Deployment"
    for container in document["spec"]["template"]["spec"]["containers"]
]
if images != [sys.argv[2]]:
    raise SystemExit(f"rendered image mismatch: expected={sys.argv[2]} actual={images}")
PY

for manifest in "$BUNDLE_DIR/manifests/reader-rbac.yaml" "$tmp_dir/kustomize-rendered.yaml"; do
  kubectl apply --dry-run=client --validate=false -f "$manifest" >/dev/null
done

if test "$LIVE_VALIDATE" = "1"; then
  kubectl --context "$HOST_CONTEXT" apply --dry-run=server \
    -f "$tmp_dir/kustomize-rendered.yaml" >/dev/null
fi

"$REPO_ROOT/scripts/public-safe-scan.sh" "$BUNDLE_DIR"
git -C "$REPO_ROOT" diff --check

echo "VERIFY_BUNDLE_OK chart=$CHART_VERSION image=$IMAGE_VERSION live_validate=$LIVE_VALIDATE"
