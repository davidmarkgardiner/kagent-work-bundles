#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"
RELEASE_NAME=${RELEASE_NAME:-kubernetes-mcp-fleet}
SECRET_NAME=${1:-${SECRET_NAME:-}}

test -n "$SECRET_NAME" || {
  echo "usage: $0 IMMUTABLE_KUBECONFIG_SECRET_NAME" >&2
  exit 1
}
test -f "$CHART_REF/Chart.yaml" || {
  echo "local Helm chart not found: $CHART_REF/Chart.yaml" >&2
  exit 1
}
actual_chart_version=$(helm show chart "$CHART_REF" | awk '$1 == "version:" {print $2; exit}')
test "$actual_chart_version" = "$CHART_VERSION" || {
  echo "chart version mismatch: expected=$CHART_VERSION actual=$actual_chart_version" >&2
  exit 1
}

kubectl --context "$HOST_CONTEXT" apply -k "$BUNDLE_DIR" >/dev/null
kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" >/dev/null
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.immutable}')" = "true"
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o json | jq -r '.metadata.labels["kubernetes-mcp-fleet/credential"] // ""')" = "true"

# shellcheck disable=SC2206
tools=( $TOOL_ALLOWLIST_LIST )
tool_set_args=()
for tool_index in "${!tools[@]}"; do
  tool_set_args+=(--set-string "config.enabled_tools[$tool_index]=${tools[$tool_index]}")
done

helm template "$RELEASE_NAME" "$CHART_REF" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set replicaCount="$REPLICA_COUNT" \
  --set-string resources.requests.cpu="$RESOURCE_REQUEST_CPU" \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${tool_set_args[@]}" \
  --set-string kubeconfigSecretName="$SECRET_NAME" >/dev/null

helm --kube-context "$HOST_CONTEXT" upgrade --install "$RELEASE_NAME" \
  "$CHART_REF" \
  --namespace "$HOST_NAMESPACE" --create-namespace \
  -f "$BUNDLE_DIR/values.yaml" \
  --set replicaCount="$REPLICA_COUNT" \
  --set-string resources.requests.cpu="$RESOURCE_REQUEST_CPU" \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${tool_set_args[@]}" \
  --set-string kubeconfigSecretName="$SECRET_NAME" \
  --wait --timeout 5m

kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" rollout status \
  deployment/kubernetes-mcp-fleet --timeout=5m

mounted_secret=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" \
  get deployment kubernetes-mcp-fleet \
  -o jsonpath='{.spec.template.spec.volumes[?(@.name=="fleet-kubeconfig")].secret.secretName}')
test "$mounted_secret" = "$SECRET_NAME"
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get deployment kubernetes-mcp-fleet -o jsonpath='{.spec.template.spec.automountServiceAccountToken}')" = "false"
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get deployment kubernetes-mcp-fleet -o jsonpath='{.spec.template.metadata.annotations.kubernetes-mcp-fleet/credential-revision}')" = "$SECRET_NAME"

old_secrets=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secrets \
  -l kubernetes-mcp-fleet/credential=true -o json | \
  jq -r --arg active "$SECRET_NAME" '.items[].metadata.name | select(. != $active)')
for old_secret in $old_secrets; do
  kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" delete secret "$old_secret" >/dev/null
done

echo "DEPLOY_OK release=$RELEASE_NAME namespace=$HOST_NAMESPACE secret=$SECRET_NAME replicas=$REPLICA_COUNT cpu_request=$RESOURCE_REQUEST_CPU tools=$TOOL_COUNT old_secrets_pruned=$(printf '%s\n' "$old_secrets" | sed '/^$/d' | wc -l | tr -d ' ')"
