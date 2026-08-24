#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${HOST_CONTEXT:?set HOST_CONTEXT to the management-cluster kubeconfig context}"
: "${SOURCE_CONTEXTS:?set SOURCE_CONTEXTS to space-separated source-context=stable-alias mappings}"

kubectl --context "$HOST_CONTEXT" delete -f "$BUNDLE_DIR/manifests/kagent-agent.yaml" --ignore-not-found >/dev/null
kubectl --context "$HOST_CONTEXT" delete -f "$BUNDLE_DIR/manifests/agentgateway-kagent.yaml" --ignore-not-found >/dev/null
helm --kube-context "$HOST_CONTEXT" uninstall kubernetes-mcp-fleet \
  --namespace kubernetes-mcp-poc --ignore-not-found >/dev/null
kubectl --context "$HOST_CONTEXT" delete namespace kubernetes-mcp-poc --ignore-not-found >/dev/null

for mapping in $SOURCE_CONTEXTS; do
  source_context=${mapping%%=*}
  kubectl --context "$source_context" delete -f "$BUNDLE_DIR/manifests/reader-rbac.yaml" \
    --ignore-not-found >/dev/null
done

echo "TEARDOWN_OK"
