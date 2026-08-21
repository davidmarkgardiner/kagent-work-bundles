#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --values /path/to/private/values.env [--stage alloy|vector|all]" >&2
  exit 2
}

[[ "${1:-}" == "--values" && -n "${2:-}" ]] || usage
VALUES="$2"
STAGE="${4:-all}"
[[ -f "$VALUES" ]] || { echo "Values file not found: $VALUES" >&2; exit 2; }
[[ "$STAGE" == "all" || "$STAGE" == "alloy" || "$STAGE" == "vector" ]] || usage

# Operator-selected values file is validated above.
set -a
# shellcheck disable=SC1090
source "$VALUES"
set +a
: "${WORKER_CONTEXT:?WORKER_CONTEXT is required}"
: "${WORKER_NAMESPACE:?WORKER_NAMESPACE is required}"
: "${ALLOY_DEPLOYMENT:?ALLOY_DEPLOYMENT is required}"
: "${ALLOY_SERVICE_ACCOUNT:?ALLOY_SERVICE_ACCOUNT is required}"
: "${VECTOR_DEPLOYMENT:?VECTOR_DEPLOYMENT is required}"
: "${VECTOR_SERVICE:?VECTOR_SERVICE is required}"
: "${ALLOY_EXPECTED_IMAGE:?ALLOY_EXPECTED_IMAGE is required}"
: "${VECTOR_EXPECTED_IMAGE:?VECTOR_EXPECTED_IMAGE is required}"

kc() { kubectl --context "$WORKER_CONTEXT" -n "$WORKER_NAMESPACE" "$@"; }
require_can_i() {
  local resource="$1"
  local answer
  answer="$(kc auth can-i get "$resource" --as "system:serviceaccount:${WORKER_NAMESPACE}:${ALLOY_SERVICE_ACCOUNT}")"
  [[ "$answer" == "yes" ]] || { echo "Alloy service account cannot get ${resource}: ${answer}" >&2; exit 1; }
  echo "RBAC_OK get ${resource}"
}
require_image() {
  local deployment="$1" expected="$2" actual
  actual="$(kc get deployment "$deployment" -o jsonpath='{range .spec.template.spec.containers[*]}{.image}{"\n"}{end}')"
  printf '%s\n' "$actual"
  grep -Fqx "$expected" <<<"$actual" || { echo "Expected image not configured on ${deployment}: ${expected}" >&2; exit 1; }
  echo "IMAGE_OK ${deployment}=${expected}"
}

echo "== Context and namespace =="
kubectl --context "$WORKER_CONTEXT" config current-context
kc get namespace "$WORKER_NAMESPACE"

if [[ "$STAGE" == "all" || "$STAGE" == "alloy" ]]; then
  echo "== Alloy deployment, RBAC and forward target =="
  kc rollout status "deployment/${ALLOY_DEPLOYMENT}" --timeout=180s
  kc get deployment "$ALLOY_DEPLOYMENT" -o wide
  require_image "$ALLOY_DEPLOYMENT" "$ALLOY_EXPECTED_IMAGE"
  require_can_i pods
  require_can_i pods/log
  require_can_i events
  kc get endpoints "$VECTOR_SERVICE" -o wide
  kc logs "deployment/${ALLOY_DEPLOYMENT}" --tail=100
fi

if [[ "$STAGE" == "all" || "$STAGE" == "vector" ]]; then
  echo "== Vector deployment and Kafka delivery symptoms =="
  kc rollout status "deployment/${VECTOR_DEPLOYMENT}" --timeout=180s
  kc get deployment "$VECTOR_DEPLOYMENT" -o wide
  require_image "$VECTOR_DEPLOYMENT" "$VECTOR_EXPECTED_IMAGE"
  [[ -z "${VECTOR_BUFFER_PVC:-}" ]] || kc get pvc "$VECTOR_BUFFER_PVC" -o wide
  kc get endpoints "$VECTOR_SERVICE" -o wide
  kc logs "deployment/${VECTOR_DEPLOYMENT}" --tail=150
  echo "== Scan Vector logs for broker/auth failures (empty output is expected) =="
  kc logs "deployment/${VECTOR_DEPLOYMENT}" --tail=300 | rg -i 'authorization|authentication|sasl|tls|certificate|broker.*error|kafka.*error' || true
fi

echo "WORKER_CHECK_COMPLETE: confirm the controlled marker in Alloy/Vector logs and Confluent portal before proceeding."
