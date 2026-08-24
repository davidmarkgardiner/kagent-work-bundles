#!/usr/bin/env bash
set -euo pipefail
set +x

: "${HOST_CONTEXT:?set HOST_CONTEXT to the management-cluster kubeconfig context}"
HOST_NAMESPACE=${HOST_NAMESPACE:-kubernetes-mcp-poc}
: "${SOURCE_CONTEXTS:?set SOURCE_CONTEXTS to space-separated source-context=stable-alias mappings}"
TOKEN_DURATION=${TOKEN_DURATION:-24h}
SECRET_PREFIX=${SECRET_PREFIX:-kubernetes-mcp-fleet-kubeconfig}
READER_NAMESPACE=${READER_NAMESPACE:-kubernetes-mcp-reader}
READER_SERVICE_ACCOUNT=${READER_SERVICE_ACCOUNT:-kubernetes-mcp-reader}

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kubernetes-mcp-fleet.XXXXXX")
chmod 700 "$tmp_dir"
fleet_kubeconfig=$(mktemp "$tmp_dir/kubeconfig.XXXXXX")
chmod 600 "$fleet_kubeconfig"

cleanup() {
  if test -f "$fleet_kubeconfig"; then
    unlink "$fleet_kubeconfig"
  fi
  rmdir "$tmp_dir" 2>/dev/null || true
}
trap cleanup EXIT

first_alias=""
expected_aliases=""

for mapping in $SOURCE_CONTEXTS; do
  source_context=${mapping%%=*}
  alias_name=${mapping#*=}
  echo "CREDENTIAL_BUILD_START source=$source_context alias=$alias_name" >&2
  case "$alias_name" in
    *[!a-zA-Z0-9._-]*|'')
      echo "invalid context alias: $alias_name" >&2
      exit 1
      ;;
  esac

  flattened=$(kubectl config view --raw --flatten --minify \
    --context "$source_context" -o json)
  server=$(printf '%s' "$flattened" | jq -er '.clusters[0].cluster.server')
  insecure=$(printf '%s' "$flattened" | jq -r '.clusters[0].cluster["insecure-skip-tls-verify"] // false')

  ca_file=$(mktemp "$tmp_dir/ca.XXXXXX")
  test "$insecure" = "false" || {
    echo "refusing insecure bootstrap context: $source_context" >&2
    exit 1
  }
  ca_data=$(printf '%s' "$flattened" | jq -er '.clusters[0].cluster["certificate-authority-data"]')
  printf '%s' "$ca_data" | openssl base64 -d -A -out "$ca_file"
  fleet_server=$server
  curl --fail --silent --cacert "$ca_file" "$server/readyz" >/dev/null
  token=$(kubectl --context "$source_context" -n "$READER_NAMESPACE" \
    create token "$READER_SERVICE_ACCOUNT" --duration "$TOKEN_DURATION")
  echo "CREDENTIAL_TOKEN_ISSUED alias=$alias_name duration=$TOKEN_DURATION" >&2

  kubectl --kubeconfig /dev/null --server "$server" --certificate-authority "$ca_file" \
    --token "$token" get --raw=/readyz >/dev/null
  test "$(kubectl --kubeconfig /dev/null --server "$server" --certificate-authority "$ca_file" \
    --token "$token" auth can-i list pods --all-namespaces)" = "yes"
  denied_secret_read=$(kubectl --kubeconfig /dev/null --server "$server" --certificate-authority "$ca_file" \
    --token "$token" auth can-i get secrets --all-namespaces || true)
  test "$denied_secret_read" = "no"
  echo "CREDENTIAL_AUTH_CHECK_OK alias=$alias_name" >&2

  kubectl config --kubeconfig "$fleet_kubeconfig" set-cluster "$alias_name" \
    --server "$fleet_server" --certificate-authority "$ca_file" --embed-certs=true >/dev/null
  kubectl config --kubeconfig "$fleet_kubeconfig" set-credentials "$alias_name-reader" \
    --token "$token" >/dev/null
  kubectl config --kubeconfig "$fleet_kubeconfig" set-context "$alias_name" \
    --cluster "$alias_name" --user "$alias_name-reader" >/dev/null
  echo "CREDENTIAL_CONTEXT_BUILT alias=$alias_name" >&2

  unset token flattened ca_data server
  unlink "$ca_file"

  if test -z "$first_alias"; then
    first_alias=$alias_name
  fi
  expected_aliases="$expected_aliases$alias_name\n"
done

echo "CREDENTIAL_BUILD_COMPLETE" >&2

kubectl config --kubeconfig "$fleet_kubeconfig" use-context "$first_alias" >/dev/null

actual_aliases=$(kubectl config --kubeconfig "$fleet_kubeconfig" get-contexts -o name | LC_ALL=C sort)
expected_aliases=$(printf '%b' "$expected_aliases" | sed '/^$/d' | LC_ALL=C sort)
test "$actual_aliases" = "$expected_aliases" || {
  echo "generated kubeconfig context allowlist mismatch" >&2
  exit 1
}

for alias_name in $actual_aliases; do
  kubectl --kubeconfig "$fleet_kubeconfig" --context "$alias_name" get --raw=/readyz >/dev/null
  test "$(kubectl --kubeconfig "$fleet_kubeconfig" --context "$alias_name" auth can-i list pods --all-namespaces)" = "yes"
  denied_secret_read=$(kubectl --kubeconfig "$fleet_kubeconfig" --context "$alias_name" \
    auth can-i get secrets --all-namespaces || true)
  test "$denied_secret_read" = "no"
  echo "CREDENTIAL_VALIDATION_OK context=$alias_name" >&2
done

secret_resource=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" \
  create secret generic "$SECRET_PREFIX" --append-hash --dry-run=client \
  --from-file=kubeconfig="$fleet_kubeconfig" -o name)
secret_name=${secret_resource#secret/}

if ! kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$secret_name" >/dev/null 2>&1; then
  kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" \
    create secret generic "$SECRET_PREFIX" --append-hash \
    --from-file=kubeconfig="$fleet_kubeconfig" >/dev/null
  kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" patch secret "$secret_name" \
    --type merge -p '{"immutable":true}' >/dev/null
fi

kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" annotate secret "$secret_name" \
  kubernetes-mcp-fleet/context-count="$(printf '%s\n' "$actual_aliases" | wc -l | tr -d ' ')" \
  kubernetes-mcp-fleet/validated-at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --overwrite >/dev/null

echo "$secret_name"
