#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${HOST_CONTEXT:?set HOST_CONTEXT to the management-cluster kubeconfig context}"
HOST_NAMESPACE=${HOST_NAMESPACE:-kubernetes-mcp-poc}
RELEASE_NAME=${RELEASE_NAME:-kubernetes-mcp-fleet}
REPLICA_COUNT=${REPLICA_COUNT:-1}
RESOURCE_REQUEST_CPU=${RESOURCE_REQUEST_CPU:-100m}
CHART_REF=${CHART_REF:-oci://ghcr.io/containers/charts/kubernetes-mcp-server}
CHART_VERSION=${CHART_VERSION:-0.1.0}
IMAGE_VERSION=${IMAGE_VERSION:-latest}
SECRET_NAME=${1:-${SECRET_NAME:-}}

test -n "$SECRET_NAME" || {
  echo "usage: $0 IMMUTABLE_KUBECONFIG_SECRET_NAME" >&2
  exit 1
}

kubectl --context "$HOST_CONTEXT" apply -f "$BUNDLE_DIR/manifests/namespace-networkpolicy.yaml" >/dev/null
kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" >/dev/null
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.immutable}')" = "true"

helm template "$RELEASE_NAME" "$CHART_REF" --version "$CHART_VERSION" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set replicaCount="$REPLICA_COUNT" \
  --set-string resources.requests.cpu="$RESOURCE_REQUEST_CPU" \
  --set-string image.version="$IMAGE_VERSION" \
  --set-string kubeconfigSecretName="$SECRET_NAME" >/dev/null

helm --kube-context "$HOST_CONTEXT" upgrade --install "$RELEASE_NAME" \
  "$CHART_REF" --version "$CHART_VERSION" \
  --namespace "$HOST_NAMESPACE" --create-namespace \
  -f "$BUNDLE_DIR/values.yaml" \
  --set replicaCount="$REPLICA_COUNT" \
  --set-string resources.requests.cpu="$RESOURCE_REQUEST_CPU" \
  --set-string image.version="$IMAGE_VERSION" \
  --set-string kubeconfigSecretName="$SECRET_NAME" \
  --wait --timeout 5m

kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" rollout status \
  deployment/kubernetes-mcp-fleet --timeout=5m

mounted_secret=$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" \
  get deployment kubernetes-mcp-fleet \
  -o jsonpath='{.spec.template.spec.volumes[?(@.name=="fleet-kubeconfig")].secret.secretName}')
test "$mounted_secret" = "$SECRET_NAME"
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get deployment kubernetes-mcp-fleet -o jsonpath='{.spec.template.spec.automountServiceAccountToken}')" = "false"

echo "DEPLOY_OK release=$RELEASE_NAME namespace=$HOST_NAMESPACE secret=$SECRET_NAME replicas=$REPLICA_COUNT cpu_request=$RESOURCE_REQUEST_CPU"
