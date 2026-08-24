#!/usr/bin/env bash
set -euo pipefail

umask 077

REGISTRY_PATH="${REGISTRY_PATH:-/etc/fleet-registry/clusters.json}"
WORK_DIR="${WORK_DIR:-/work}"
TARGET_NAMESPACE="${TARGET_NAMESPACE:-aks-mcp}"
FLEET_SECRET_NAME="${FLEET_SECRET_NAME:-aks-mcp-fleet-kubeconfig}"
MCP_DEPLOYMENT_PREFIX="${MCP_DEPLOYMENT_PREFIX:-aks-mcp-}"
STATIC_SOURCE_DIR="${STATIC_SOURCE_DIR:-/var/run/fleet-source}"
ALLOW_STATIC_SOURCES="${ALLOW_STATIC_SOURCES:-false}"
ALLOW_STATIC_CREDENTIALS="${ALLOW_STATIC_CREDENTIALS:-false}"
SKIP_CONNECTIVITY="${SKIP_CONNECTIVITY:-false}"
VALIDATE_ONLY="${VALIDATE_ONLY:-false}"
ROLLOUT_ON_CHANGE="${ROLLOUT_ON_CHANGE:-true}"
ROLLOUT_MAX_PARALLEL="${ROLLOUT_MAX_PARALLEL:-4}"
CONTROL_CONTEXT="${CONTROL_CONTEXT:-}"

CONTROL_KUBECTL=(kubectl)
if [[ -n "$CONTROL_CONTEXT" ]]; then
  CONTROL_KUBECTL=(kubectl --context "$CONTROL_CONTEXT")
fi

fail() {
  printf 'FLEET_REFRESH_FAILED: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command is missing: $1"
}

for command_name in jq kubectl sha256sum; do
  require_command "$command_name"
done

[[ -f "$REGISTRY_PATH" ]] || fail "registry file does not exist: $REGISTRY_PATH"
mkdir -p "$WORK_DIR"
CANDIDATE_PATH="$WORK_DIR/fleet.kubeconfig"
NEXT_PATH="$WORK_DIR/next.kubeconfig"
NORMALIZED_PATH="$WORK_DIR/normalized.kubeconfig"
LIVE_SECRET_PATH="$WORK_DIR/live-secret.json"
NEW_SECRET_PATH="$WORK_DIR/new-secret.json"
REPLACEMENT_PATH="$WORK_DIR/replacement-secret.json"
SHARD_DIR="$WORK_DIR/shards"
rm -f "$CANDIDATE_PATH" "$NEXT_PATH" "$NORMALIZED_PATH" \
  "$LIVE_SECRET_PATH" "$NEW_SECRET_PATH" "$REPLACEMENT_PATH"
rm -rf "$SHARD_DIR"
mkdir -p "$SHARD_DIR"

cluster_count="$(jq -er '.clusters | length' "$REGISTRY_PATH")" \
  || fail "registry must contain a clusters array"
[[ "$cluster_count" -gt 0 ]] || fail "registry contains no clusters"

alias_lines="$(jq -er '.clusters[].alias' "$REGISTRY_PATH")" \
  || fail "every cluster requires an alias"
while IFS= read -r alias_name; do
  [[ "$alias_name" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] \
    || fail "invalid alias; use 1-63 lowercase letters, digits, or hyphens"
done <<<"$alias_lines"

unique_count="$(printf '%s\n' "$alias_lines" | sort -u | wc -l | tr -d ' ')"
[[ "$unique_count" == "$cluster_count" ]] || fail "cluster aliases must be unique"

aks_count="$(jq '[.clusters[] | select(.provider == "aks")] | length' "$REGISTRY_PATH")"
has_aks=false
if [[ "$aks_count" -gt 0 ]]; then
  has_aks=true
  require_command az
  require_command kubelogin
  : "${AZURE_CLIENT_ID:?AZURE_CLIENT_ID is required for AKS workload identity}"
  : "${AZURE_TENANT_ID:?AZURE_TENANT_ID is required for AKS workload identity}"
  : "${AZURE_FEDERATED_TOKEN_FILE:?AZURE_FEDERATED_TOKEN_FILE is required for AKS workload identity}"
  [[ -r "$AZURE_FEDERATED_TOKEN_FILE" ]] \
    || fail "Azure federated token file is not readable"
  export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-$WORK_DIR/.azure}"
  mkdir -p "$AZURE_CONFIG_DIR"
  federated_token="$(<"$AZURE_FEDERATED_TOKEN_FILE")"
  [[ -n "$federated_token" ]] || fail "Azure federated token file is empty"
  az login --service-principal \
    --username "$AZURE_CLIENT_ID" \
    --tenant "$AZURE_TENANT_ID" \
    --federated-token "$federated_token" \
    --only-show-errors --output none \
    || fail "Azure workload identity login failed"
  unset federated_token
  az account show --only-show-errors --output none \
    || fail "Azure CLI has no active subscription after login"
fi

merge_normalized() {
  local source_file="$1"
  local alias_name="$2"
  local context_count source_context

  cp "$source_file" "$NORMALIZED_PATH"
  context_count="$(kubectl --kubeconfig "$NORMALIZED_PATH" config get-contexts -o name | wc -l | tr -d ' ')"
  [[ "$context_count" == "1" ]] \
    || fail "static source for alias $alias_name must contain exactly one context"
  source_context="$(kubectl --kubeconfig "$NORMALIZED_PATH" config get-contexts -o name)"
  if [[ "$source_context" != "$alias_name" ]]; then
    kubectl --kubeconfig "$NORMALIZED_PATH" config rename-context \
      "$source_context" "$alias_name" >/dev/null
  fi
  kubectl --kubeconfig "$NORMALIZED_PATH" config unset current-context >/dev/null 2>&1 || true

  if [[ ! -f "$CANDIDATE_PATH" ]]; then
    cp "$NORMALIZED_PATH" "$CANDIDATE_PATH"
  else
    KUBECONFIG="$CANDIDATE_PATH:$NORMALIZED_PATH" \
      kubectl config view --flatten --raw >"$NEXT_PATH"
    mv "$NEXT_PATH" "$CANDIDATE_PATH"
  fi
}

for index in $(seq 0 $((cluster_count - 1))); do
  alias_name="$(jq -er ".clusters[$index].alias" "$REGISTRY_PATH")"
  provider="$(jq -er ".clusters[$index].provider" "$REGISTRY_PATH")"

  case "$provider" in
    aks)
      subscription_id="$(jq -er ".clusters[$index].subscriptionId" "$REGISTRY_PATH")"
      resource_group="$(jq -er ".clusters[$index].resourceGroup" "$REGISTRY_PATH")"
      cluster_name="$(jq -er ".clusters[$index].clusterName" "$REGISTRY_PATH")"
      az aks get-credentials \
        --subscription "$subscription_id" \
        --resource-group "$resource_group" \
        --name "$cluster_name" \
        --context "$alias_name" \
        --file "$CANDIDATE_PATH" \
        --format exec \
        --overwrite-existing \
        --only-show-errors >/dev/null
      ;;
    static)
      [[ "$ALLOW_STATIC_SOURCES" == "true" ]] \
        || fail "static source requested but ALLOW_STATIC_SOURCES is not true"
      source_name="$(jq -er ".clusters[$index].sourceFile" "$REGISTRY_PATH")"
      [[ "$source_name" =~ ^[a-zA-Z0-9._-]+$ ]] \
        || fail "static sourceFile contains unsafe characters"
      source_path="$STATIC_SOURCE_DIR/$source_name"
      [[ -f "$source_path" ]] || fail "static source file is missing for alias $alias_name"
      merge_normalized "$source_path" "$alias_name"
      ;;
    *)
      fail "unsupported provider for alias $alias_name"
      ;;
  esac
done

[[ -s "$CANDIDATE_PATH" ]] || fail "candidate kubeconfig was not created"
if [[ "$has_aks" == "true" ]]; then
  kubelogin convert-kubeconfig \
    --login workloadidentity \
    --client-id "$AZURE_CLIENT_ID" \
    --tenant-id "$AZURE_TENANT_ID" \
    --kubeconfig "$CANDIDATE_PATH"
fi
kubectl --kubeconfig "$CANDIDATE_PATH" config unset current-context >/dev/null 2>&1 || true

candidate_json="$(kubectl --kubeconfig "$CANDIDATE_PATH" config view --raw -o json)"
expected_aliases="$(printf '%s\n' "$alias_lines" | sort)"
actual_aliases="$(jq -r '.contexts[].name' <<<"$candidate_json" | sort)"
[[ "$actual_aliases" == "$expected_aliases" ]] \
  || fail "candidate contexts do not exactly match the approved registry"

credential_count="$(jq '[.users[].user | select(
  has("token") or has("tokenFile") or has("password") or
  has("client-certificate-data") or has("client-key-data")
)] | length' <<<"$candidate_json")"
if [[ "$credential_count" -gt 0 && "$ALLOW_STATIC_CREDENTIALS" != "true" ]]; then
  fail "candidate contains embedded credentials; only exec-based identities are allowed"
fi

if [[ "$has_aks" == "true" ]]; then
  bad_exec_count="$(jq '[.contexts[] as $context
    | .users[]
    | select(.name == $context.context.user)
    | select((.user.exec.command // "") | contains("kubelogin") | not)
  ] | length' <<<"$candidate_json")"
  [[ "$bad_exec_count" == "0" ]] \
    || fail "one or more AKS contexts do not use kubelogin exec authentication"
fi

if [[ "$SKIP_CONNECTIVITY" != "true" ]]; then
  while IFS=$'\t' read -r alias_name smoke_namespace; do
    kubectl --kubeconfig "$CANDIDATE_PATH" --context "$alias_name" \
      --request-timeout=15s get namespace "$smoke_namespace" -o name >/dev/null
    kubectl --kubeconfig "$CANDIDATE_PATH" --context "$alias_name" \
      --request-timeout=15s auth can-i get pods --namespace "$smoke_namespace" \
      | grep -qx yes \
      || fail "read-only pod access check failed for alias $alias_name"
  done < <(jq -r '.clusters[] | [.alias, (.smokeNamespace // "kube-system")] | @tsv' "$REGISTRY_PATH")
fi

# AKS-MCP intentionally blocks --context and --kubeconfig in tool calls. Split
# the validated candidate into one current-context file per approved alias so
# each MCP shard receives only the target it is allowed to reach.
while IFS= read -r alias_name; do
  shard_path="$SHARD_DIR/$alias_name.config"
  kubectl --kubeconfig "$CANDIDATE_PATH" --context "$alias_name" \
    config view --minify --flatten --raw >"$shard_path"
  shard_current="$(kubectl --kubeconfig "$shard_path" config current-context)"
  [[ "$shard_current" == "$alias_name" ]] \
    || fail "single-context shard has the wrong current-context for alias $alias_name"
done <<<"$alias_lines"

secret_payload_size="$(find "$SHARD_DIR" -type f -name '*.config' -exec wc -c {} + \
  | awk '{total += $1} END {print total + 0}')"
[[ "$secret_payload_size" -lt 900000 ]] \
  || fail "single-context shard payload is too large for one Kubernetes Secret"

candidate_hash="$(sha256sum "$CANDIDATE_PATH" | awk '{print $1}')"
if [[ "$VALIDATE_ONLY" == "true" ]]; then
  printf 'VALIDATION_OK contexts=%s sha256=%s\n' "$cluster_count" "$candidate_hash"
  exit 0
fi

"${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" get secret "$FLEET_SECRET_NAME" -o json \
  >"$LIVE_SECRET_PATH" \
  || fail "destination Secret must be pre-created"
existing_hash="$(jq -r '.metadata.annotations["platform.example.com/kubeconfig-sha256"] // ""' "$LIVE_SECRET_PATH")"
secret_changed=false
if [[ "$existing_hash" != "$candidate_hash" ]]; then
  secret_create_args=(--namespace "$TARGET_NAMESPACE" create secret generic "$FLEET_SECRET_NAME")
  while IFS= read -r alias_name; do
    secret_create_args+=(--from-file="$alias_name.config=$SHARD_DIR/$alias_name.config")
  done <<<"$alias_lines"
  "${CONTROL_KUBECTL[@]}" "${secret_create_args[@]}" \
    --dry-run=client -o json >"$NEW_SECRET_PATH"
  jq --arg hash "$candidate_hash" --slurp '
    .[0] as $live | .[1] as $new |
    $live
    | .type = $new.type
    | .data = $new.data
    | .metadata.labels = ((.metadata.labels // {}) + {
        "app.kubernetes.io/part-of": "aks-mcp-fleet-kubeconfig"
      })
    | .metadata.annotations = ((.metadata.annotations // {}) + {
        "platform.example.com/kubeconfig-sha256": $hash
      })
    | del(.metadata.managedFields)
  ' "$LIVE_SECRET_PATH" "$NEW_SECRET_PATH" >"$REPLACEMENT_PATH"
  "${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" replace \
    --dry-run=server -f "$REPLACEMENT_PATH" >/dev/null \
    || fail "replacement Secret failed API validation"
  "${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" replace -f "$REPLACEMENT_PATH" >/dev/null
  secret_changed=true
fi

if [[ "$ROLLOUT_ON_CHANGE" == "true" ]]; then
  [[ "$ROLLOUT_MAX_PARALLEL" =~ ^[1-9][0-9]*$ ]] \
    || fail "ROLLOUT_MAX_PARALLEL must be a positive integer"
  rollout_patch="$(jq -cn --arg hash "$candidate_hash" \
    '{spec:{template:{metadata:{annotations:{"platform.example.com/kubeconfig-sha256":$hash}}}}}')"

  reconcile_rollout() {
    local deployment_name="$1" deployment_json applied_hash
    deployment_json="$("${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" \
      get deployment "$deployment_name" -o json)" || return 1
    applied_hash="$(jq -r '.spec.template.metadata.annotations["platform.example.com/kubeconfig-sha256"] // ""' \
      <<<"$deployment_json")"
    if [[ "$applied_hash" != "$candidate_hash" ]]; then
      "${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" patch deployment \
        "$deployment_name" --type=merge -p "$rollout_patch" >/dev/null || return 1
    fi
    "${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" rollout status deployment \
      "$deployment_name" --timeout=5m >/dev/null || return 1
    deployment_json="$("${CONTROL_KUBECTL[@]}" --namespace "$TARGET_NAMESPACE" \
      get deployment "$deployment_name" -o json)" || return 1
    applied_hash="$(jq -r '.spec.template.metadata.annotations["platform.example.com/kubeconfig-sha256"] // ""' \
      <<<"$deployment_json")"
    [[ "$applied_hash" == "$candidate_hash" ]]
  }

  rollout_pids=()
  rollout_names=()
  wait_for_rollout_batch() {
    local index batch_failed=false
    for index in "${!rollout_pids[@]}"; do
      if ! wait "${rollout_pids[$index]}"; then
        printf 'rollout failed for deployment %s\n' "${rollout_names[$index]}" >&2
        batch_failed=true
      fi
    done
    rollout_pids=()
    rollout_names=()
    [[ "$batch_failed" == "false" ]] || fail "one or more AKS-MCP shard rollouts failed"
  }

  while IFS= read -r alias_name; do
    deployment_name="$MCP_DEPLOYMENT_PREFIX$alias_name"
    reconcile_rollout "$deployment_name" &
    rollout_pids+=("$!")
    rollout_names+=("$deployment_name")
    if [[ "${#rollout_pids[@]}" -ge "$ROLLOUT_MAX_PARALLEL" ]]; then
      wait_for_rollout_batch
    fi
  done <<<"$alias_lines"
  if [[ "${#rollout_pids[@]}" -gt 0 ]]; then
    wait_for_rollout_batch
  fi
fi

if [[ "$secret_changed" == "false" ]]; then
  printf 'UNCHANGED contexts=%s sha256=%s\n' "$cluster_count" "$candidate_hash"
  exit 0
fi

printf 'PUBLISHED contexts=%s sha256=%s rollout=%s\n' \
  "$cluster_count" "$candidate_hash" "$ROLLOUT_ON_CHANGE"
