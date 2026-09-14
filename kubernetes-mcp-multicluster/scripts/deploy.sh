#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"
# shellcheck source=secret-utils.sh
source "$BUNDLE_DIR/scripts/secret-utils.sh"
RELEASE_NAME=${RELEASE_NAME:-$MCP_NAME}
SECRET_NAME=${1:-${SECRET_NAME:-}}

if test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "1"; then
  SECRET_NAME=$KUBECONFIG_SECRET_NAME
fi

test -n "$SECRET_NAME" || {
  echo "usage for the homelab proof: $0 IMMUTABLE_KUBECONFIG_SECRET_NAME" >&2
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
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o json | jq -r '.metadata.labels["kubernetes-mcp-fleet/credential"] // ""')" = "true"
test -n "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.kubeconfig}')" || {
  echo "credential Secret has not yet been populated by the refresh Job: $HOST_NAMESPACE/$SECRET_NAME" >&2
  exit 1
}
if test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "0"; then
  test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.immutable}')" = "true"
fi

previous_secret=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" \
  get deployment "$MCP_NAME" \
  -o jsonpath='{.spec.template.spec.volumes[?(@.name=="fleet-kubeconfig")].secret.secretName}' \
  2>/dev/null || true)
if test "$previous_secret" = "$SECRET_NAME"; then
  previous_secret=""
fi

# shellcheck disable=SC2206
tools=( $TOOL_ALLOWLIST_LIST )
tool_set_args=()
for tool_index in "${!tools[@]}"; do
  tool_set_args+=(--set-string "config.enabled_tools[$tool_index]=${tools[$tool_index]}")
done

identity_set_args=(
  --set-string "fullnameOverride=$MCP_NAME"
)
if test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "1"; then
  identity_set_args+=(
    --set serviceAccount.create=false
    --set-string "serviceAccount.name=$MCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT"
    --set serviceAccount.automountToken=true
  )
fi

helm template "$RELEASE_NAME" "$CHART_REF" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set replicaCount="$REPLICA_COUNT" \
  --set-string resources.requests.cpu="$RESOURCE_REQUEST_CPU" \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${identity_set_args[@]}" \
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
  "${identity_set_args[@]}" \
  "${tool_set_args[@]}" \
  --set-string kubeconfigSecretName="$SECRET_NAME" \
  --wait --timeout 5m

kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" rollout status \
  deployment/"$MCP_NAME" --timeout=5m

mounted_secret=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" \
  get deployment "$MCP_NAME" \
  -o jsonpath='{.spec.template.spec.volumes[?(@.name=="fleet-kubeconfig")].secret.secretName}')
test "$mounted_secret" = "$SECRET_NAME"
expected_automount=false
if test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "1"; then
  expected_automount=true
fi
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get deployment "$MCP_NAME" -o jsonpath='{.spec.template.spec.automountServiceAccountToken}')" = "$expected_automount"
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get deployment "$MCP_NAME" -o jsonpath='{.spec.template.metadata.annotations.kubernetes-mcp-fleet/credential-revision}')" = "$SECRET_NAME"

if test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "1"; then
  test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get deployment "$MCP_NAME" -o jsonpath='{.spec.template.spec.serviceAccountName}')" = "$MCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT"
  kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" exec deployment/"$MCP_NAME" -- kubelogin --version >/dev/null
  echo "MCP_WORKLOAD_IDENTITY_OK service_account=$HOST_NAMESPACE/$MCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT helper=kubelogin"
fi

old_secrets=""
if test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "0"; then
  old_secrets=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secrets \
    -l kubernetes-mcp-fleet/credential=true -o json | \
    credential_secrets_to_prune "$SECRET_NAME" "$previous_secret")
fi
for old_secret in $old_secrets; do
  kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" delete secret "$old_secret" >/dev/null
done

if test -z "$previous_secret"; then
  retained_previous=no
else
  retained_previous=yes
fi
echo "DEPLOY_OK release=$RELEASE_NAME namespace=$HOST_NAMESPACE secret=$SECRET_NAME replicas=$REPLICA_COUNT cpu_request=$RESOURCE_REQUEST_CPU tools=$TOOL_COUNT previous_revision_retained=$retained_previous old_secrets_pruned=$(printf '%s\n' "$old_secrets" | sed '/^$/d' | wc -l | tr -d ' ')"
