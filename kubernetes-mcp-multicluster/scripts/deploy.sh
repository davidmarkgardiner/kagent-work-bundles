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
case "$IMAGE_REGISTRY" in
  quay.io|ghcr.io|docker.io|registry-1.docker.io)
    test "$ALLOW_PUBLIC_IMAGE_FOR_TEST" = "1" || {
      echo "refusing public image registry in air-gapped mode: $IMAGE_REGISTRY" >&2
      exit 1
    }
    ;;
esac
actual_chart_version=$(helm show chart "$CHART_REF" | awk '$1 == "version:" {print $2; exit}')
test "$actual_chart_version" = "$CHART_VERSION" || {
  echo "chart version mismatch: expected=$CHART_VERSION actual=$actual_chart_version" >&2
  exit 1
}

kubectl --context "$HOST_CONTEXT" apply -k "$BUNDLE_DIR" >/dev/null
kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" >/dev/null
test "$(kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.immutable}')" = "true"

helm template "$RELEASE_NAME" "$CHART_REF" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set replicaCount="$REPLICA_COUNT" \
  --set-string resources.requests.cpu="$RESOURCE_REQUEST_CPU" \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
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
