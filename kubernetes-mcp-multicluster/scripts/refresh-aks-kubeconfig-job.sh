#!/usr/bin/env bash
set -euo pipefail

umask 077

required_variables=(
  AKS_CREDENTIAL_REFRESH_ENABLED AZURE_SUBSCRIPTION_IDS
  AKS_MCP_UAMI_CLIENT_ID
  FLEET_ENVIRONMENT HOST_NAMESPACE KUBECONFIG_SECRET_NAME MCP_NAME
)
for variable_name in "${required_variables[@]}"; do
  test -n "${!variable_name:-}" || {
    echo "missing required environment value: $variable_name" >&2
    exit 1
  }
done
test "$AKS_CREDENTIAL_REFRESH_ENABLED" = "1" || {
  echo "AKS credential refresh is disabled" >&2
  exit 1
}

for command_name in az jq kubectl kubelogin sha256sum; do
  command -v "$command_name" >/dev/null || {
    echo "credential refresh image is missing $command_name" >&2
    exit 1
  }
done
test -n "${AZURE_CLIENT_ID:-}" && test -n "${AZURE_TENANT_ID:-}" \
  && test -r "${AZURE_FEDERATED_TOKEN_FILE:-/nonexistent}" || {
  echo "Azure Workload Identity injection is missing" >&2
  exit 1
}
test "$AZURE_CLIENT_ID" = "$AKS_MCP_UAMI_CLIENT_ID" || {
  echo "injected Workload Identity client ID does not match AKS_MCP_UAMI_CLIENT_ID" >&2
  exit 1
}

work_dir=$(mktemp -d /work/aks-kubeconfig.XXXXXX)
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT
export AZURE_CONFIG_DIR="$work_dir/azure"
fleet_kubeconfig="$work_dir/kubeconfig"

az login --service-principal \
  --username "$AZURE_CLIENT_ID" \
  --tenant "$AZURE_TENANT_ID" \
  --federated-token "$(<"$AZURE_FEDERATED_TOKEN_FILE")" \
  --allow-no-subscriptions --output none

IFS=',' read -r -a subscriptions <<<"$AZURE_SUBSCRIPTION_IDS"
test "${#subscriptions[@]}" -gt 0
cluster_inventory="$work_dir/clusters.tsv"
: >"$cluster_inventory"
for subscription_id in "${subscriptions[@]}"; do
  test -n "$subscription_id" || {
    echo "AZURE_SUBSCRIPTION_IDS contains an empty entry" >&2
    exit 1
  }
  az aks list --subscription "$subscription_id" --only-show-errors -o json | \
    jq -r --arg subscription "$subscription_id" \
      '.[] | [$subscription, .resourceGroup, .name] | @tsv' >>"$cluster_inventory"
done
LC_ALL=C sort -u "$cluster_inventory" -o "$cluster_inventory"
cluster_count=$(wc -l <"$cluster_inventory" | tr -d ' ')
test "$cluster_count" -gt 0 || {
  echo "no AKS clusters were discovered for $FLEET_ENVIRONMENT" >&2
  exit 1
}

declare -A seen_contexts=()
while IFS=$'\t' read -r subscription_id resource_group cluster_name; do
  context_alias=$cluster_name
  test -n "$context_alias" || {
    echo "could not derive context alias for cluster $cluster_name" >&2
    exit 1
  }
  test -z "${seen_contexts[$context_alias]:-}" || {
    echo "duplicate cluster name across configured subscriptions: $context_alias" >&2
    exit 1
  }
  seen_contexts[$context_alias]=1

  az aks get-credentials \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$cluster_name" \
    --file "$fleet_kubeconfig" \
    --format exec \
    --context "$context_alias" \
    --overwrite-existing \
    --only-show-errors
done <"$cluster_inventory"

KUBECONFIG="$fleet_kubeconfig" kubelogin convert-kubeconfig -l workloadidentity
config_json=$(kubectl --kubeconfig "$fleet_kubeconfig" config view --raw -o json)
printf '%s' "$config_json" | jq -e '
  (.contexts | length) > 0 and
  ([.clusters[].cluster["insecure-skip-tls-verify"] // false] | all(. == false)) and
  ([.users[].user | has("token") or has("client-certificate-data") or has("client-key-data")] | all(. == false)) and
  ([.users[].user.exec.command | endswith("kubelogin")] | all) and
  ([.users[].user.exec.args | index("workloadidentity") != null] | all)
' >/dev/null || {
  echo "generated kubeconfig failed credential or TLS safety checks" >&2
  exit 1
}

mapfile -t contexts < <(kubectl --kubeconfig "$fleet_kubeconfig" config get-contexts -o name | LC_ALL=C sort)
test "${#contexts[@]}" -eq "$cluster_count" || {
  echo "context count mismatch: discovered=$cluster_count rendered=${#contexts[@]}" >&2
  exit 1
}
for context_alias in "${contexts[@]}"; do
  kubectl --kubeconfig "$fleet_kubeconfig" --context "$context_alias" \
    --request-timeout=20s get --raw=/readyz >/dev/null
  kubectl --kubeconfig "$fleet_kubeconfig" --context "$context_alias" \
    --request-timeout=20s auth can-i list pods --all-namespaces | grep -qx yes
  kubectl --kubeconfig "$fleet_kubeconfig" --context "$context_alias" \
    --request-timeout=20s auth can-i get secrets --all-namespaces | grep -qx no
done

content_hash=$(sha256sum "$fleet_kubeconfig" | awk '{print $1}')
validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
previous_kubeconfig=$(kubectl -n "$HOST_NAMESPACE" get secret "$KUBECONFIG_SECRET_NAME" \
  -o jsonpath='{.data.kubeconfig}')
previous_hash=$(kubectl -n "$HOST_NAMESPACE" get secret "$KUBECONFIG_SECRET_NAME" \
  -o jsonpath='{.metadata.annotations.kubernetes-mcp-fleet/content-sha256}')
kubectl -n "$HOST_NAMESPACE" get secret "$KUBECONFIG_SECRET_NAME" -o json | \
  jq --rawfile kubeconfig "$fleet_kubeconfig" \
    --arg environment "$FLEET_ENVIRONMENT" \
    --arg cluster_count "$cluster_count" \
    --arg content_hash "$content_hash" \
    --arg validated_at "$validated_at" '
      .data["kubeconfig.previous"] = (.data.kubeconfig // "") |
      .data.kubeconfig = ($kubeconfig | @base64) |
      .metadata.labels["app.kubernetes.io/part-of"] = "kubernetes-mcp-fleet-poc" |
      .metadata.labels["kubernetes-mcp-fleet/credential"] = "true" |
      .metadata.annotations["kubernetes-mcp-fleet/environment"] = $environment |
      .metadata.annotations["kubernetes-mcp-fleet/context-count"] = $cluster_count |
      .metadata.annotations["kubernetes-mcp-fleet/content-sha256"] = $content_hash |
      .metadata.annotations["kubernetes-mcp-fleet/validated-at"] = $validated_at |
      if .data["kubeconfig.previous"] == "" then del(.data["kubeconfig.previous"])
      else . end |
      del(.metadata.managedFields)
    ' | kubectl replace -f - >/dev/null

if kubectl -n "$HOST_NAMESPACE" get deployment "$MCP_NAME" >/dev/null 2>&1; then
  kubectl -n "$HOST_NAMESPACE" patch deployment "$MCP_NAME" --type merge \
    -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubernetes-mcp-fleet/credential-content-sha256\":\"$content_hash\"}}}}}" \
    >/dev/null
  rollout_complete=false
  for _ in $(seq 1 60); do
    deployment_status=$(kubectl -n "$HOST_NAMESPACE" get deployment "$MCP_NAME" -o json)
    if printf '%s' "$deployment_status" | jq -e '
      (.metadata.generation == (.status.observedGeneration // 0)) and
      ((.status.updatedReplicas // 0) == (.spec.replicas // 1)) and
      ((.status.availableReplicas // 0) == (.spec.replicas // 1)) and
      ((.status.unavailableReplicas // 0) == 0)
    ' >/dev/null; then
      rollout_complete=true
      break
    fi
    sleep 5
  done
  if test "$rollout_complete" != "true"; then
    if test -n "$previous_kubeconfig"; then
      kubectl -n "$HOST_NAMESPACE" get secret "$KUBECONFIG_SECRET_NAME" -o json | \
        jq --arg previous "$previous_kubeconfig" --arg previous_hash "$previous_hash" '
          .data.kubeconfig = $previous |
          .metadata.annotations["kubernetes-mcp-fleet/content-sha256"] = $previous_hash |
          del(.data["kubeconfig.previous"], .metadata.managedFields)
        ' | kubectl replace -f - >/dev/null
      kubectl -n "$HOST_NAMESPACE" patch deployment "$MCP_NAME" --type merge \
        -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"kubernetes-mcp-fleet/credential-content-sha256\":\"rollback-${previous_hash:-$validated_at}\"}}}}}" \
        >/dev/null
      echo "MCP rollout failed; restored the preceding kubeconfig" >&2
    else
      echo "MCP rollout failed and no preceding kubeconfig exists" >&2
    fi
    exit 1
  fi
fi

echo "AKS_KUBECONFIG_REFRESH_OK environment=$FLEET_ENVIRONMENT contexts=$cluster_count secret=$HOST_NAMESPACE/$KUBECONFIG_SECRET_NAME hash=$content_hash"
