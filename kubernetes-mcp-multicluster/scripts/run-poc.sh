#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"

test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "0" || {
  echo "run-poc.sh is homelab-only; run the Kubernetes credential Job for AKS" >&2
  exit 1
}

"$BUNDLE_DIR/scripts/preflight.sh"
kubectl --context "$HOST_CONTEXT" apply -k "$BUNDLE_DIR" >/dev/null
"$BUNDLE_DIR/scripts/install-readers.sh"
secret_name=$("$BUNDLE_DIR/scripts/refresh-kubeconfig.sh")
"$BUNDLE_DIR/scripts/deploy.sh" "$secret_name"
"$BUNDLE_DIR/scripts/register.sh"
"$BUNDLE_DIR/scripts/smoke.sh"

echo "POC_OK host=$HOST_CONTEXT secret=$secret_name agent=$KAGENT_NAMESPACE/$KAGENT_AGENT_NAME"
