#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"

helm --kube-context "$HOST_CONTEXT" uninstall "$MCP_NAME" \
  --namespace "$HOST_NAMESPACE" --ignore-not-found >/dev/null
kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" delete secret \
  -l kubernetes-mcp-fleet/credential=true --ignore-not-found >/dev/null
kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" delete remotemcpserver \
  kubernetes-mcp-fleet-direct --ignore-not-found >/dev/null
kubectl --context "$HOST_CONTEXT" delete -k "$BUNDLE_DIR" --ignore-not-found >/dev/null

for mapping in $SOURCE_CONTEXTS_LIST; do
  source_context=${mapping%%=*}
  kubectl --context "$source_context" delete -f "$BUNDLE_DIR/manifests/reader-rbac.yaml" \
    --ignore-not-found >/dev/null
done

echo "TEARDOWN_OK"
