#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"
READER_SUBJECT=system:serviceaccount:kubernetes-mcp-reader:kubernetes-mcp-reader

for mapping in $SOURCE_CONTEXTS_LIST; do
  source_context=${mapping%%=*}
  kubectl --context "$source_context" apply -f "$BUNDLE_DIR/manifests/reader-rbac.yaml" >/dev/null

  for allowed in \
    "get namespaces" \
    "list nodes" \
    "list pods --all-namespaces" \
    "get pods/log --all-namespaces" \
    "list events --all-namespaces" \
    "list deployments.apps --all-namespaces"; do
    # shellcheck disable=SC2086
    result=$(kubectl --context "$source_context" auth can-i $allowed --as="$READER_SUBJECT")
    test "$result" = "yes" || {
      echo "reader allow check failed: context=$source_context operation=$allowed" >&2
      exit 1
    }
  done

  for denied in \
    "get secrets --all-namespaces" \
    "list serviceaccounts --all-namespaces" \
    "list roles.rbac.authorization.k8s.io --all-namespaces" \
    "create pods --all-namespaces" \
    "delete pods --all-namespaces" \
    "create pods/exec --all-namespaces" \
    "create serviceaccounts/token --namespace kubernetes-mcp-reader"; do
    # shellcheck disable=SC2086
    result=$(kubectl --context "$source_context" auth can-i $denied \
      --as="$READER_SUBJECT" || true)
    test "$result" = "no" || {
      echo "reader deny check failed: context=$source_context operation=$denied" >&2
      exit 1
    }
  done
  echo "READER_RBAC_OK context=$source_context"
done
