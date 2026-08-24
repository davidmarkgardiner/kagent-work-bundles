#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${HOST_CONTEXT:?set HOST_CONTEXT to the management-cluster kubeconfig context}"

"$BUNDLE_DIR/scripts/preflight.sh"
kubectl --context "$HOST_CONTEXT" apply -f "$BUNDLE_DIR/manifests/namespace-networkpolicy.yaml" >/dev/null
"$BUNDLE_DIR/scripts/install-readers.sh"
secret_name=$("$BUNDLE_DIR/scripts/refresh-kubeconfig.sh")
"$BUNDLE_DIR/scripts/deploy.sh" "$secret_name"
"$BUNDLE_DIR/scripts/register.sh"
"$BUNDLE_DIR/scripts/smoke.sh"

echo "POC_OK host=$HOST_CONTEXT secret=$secret_name agent=kagent/kubernetes-mcp-fleet-agent"
