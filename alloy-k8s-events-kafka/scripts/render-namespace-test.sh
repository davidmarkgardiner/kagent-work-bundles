#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 OUT_DIR" >&2
  exit 2
fi

required_env=(
  WORKLOAD_KUBE_CONTEXT
  TEST_NAMESPACE
  MONITORING_NAMESPACE
  ARGO_EVENTS_NAMESPACE
  ARGO_WORKFLOWS_NAMESPACE
  ARGO_EVENTS_SERVICE_ACCOUNT
  ARGO_EVENTS_EVENTBUS_NAME
  CONFLUENT_BOOTSTRAP
  CONFLUENT_K8S_EVENTS_TOPIC
  ALLOY_CONFLUENT_SECRET_NAME
  CONFLUENT_CREDENTIALS_SECRET_NAME
  CONFLUENT_CA_SECRET_NAME
  CONSUMER_GROUP_PREFIX
  CLUSTER_NAME
  CLUSTER_ENVIRONMENT
  CLUSTER_REGION
)

missing=()
for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "missing required environment variables:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

out_dir="$1"
bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src_dir="$bundle_root/examples/namespace-scoped"

rm -rf "$out_dir"
mkdir -p "$out_dir"
cp "$src_dir"/*.yaml "$out_dir"/

replace() {
  local key="$1"
  local value="$2"
  find "$out_dir" -type f -name '*.yaml' -print0 |
    xargs -0 perl -pi -e "s/\\{\\{$key\\}\\}/$value/g"
}

escape_for_perl() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

replace "WORKLOAD_KUBE_CONTEXT" "$(escape_for_perl "$WORKLOAD_KUBE_CONTEXT")"
replace "TEST_NAMESPACE" "$(escape_for_perl "$TEST_NAMESPACE")"
replace "MONITORING_NAMESPACE" "$(escape_for_perl "$MONITORING_NAMESPACE")"
replace "ARGO_EVENTS_NAMESPACE" "$(escape_for_perl "$ARGO_EVENTS_NAMESPACE")"
replace "ARGO_WORKFLOWS_NAMESPACE" "$(escape_for_perl "$ARGO_WORKFLOWS_NAMESPACE")"
replace "ARGO_EVENTS_SERVICE_ACCOUNT" "$(escape_for_perl "$ARGO_EVENTS_SERVICE_ACCOUNT")"
replace "ARGO_EVENTS_EVENTBUS_NAME" "$(escape_for_perl "$ARGO_EVENTS_EVENTBUS_NAME")"
replace "CONFLUENT_BOOTSTRAP" "$(escape_for_perl "$CONFLUENT_BOOTSTRAP")"
replace "CONFLUENT_K8S_EVENTS_TOPIC" "$(escape_for_perl "$CONFLUENT_K8S_EVENTS_TOPIC")"
replace "ALLOY_CONFLUENT_SECRET_NAME" "$(escape_for_perl "$ALLOY_CONFLUENT_SECRET_NAME")"
replace "CONFLUENT_CREDENTIALS_SECRET_NAME" "$(escape_for_perl "$CONFLUENT_CREDENTIALS_SECRET_NAME")"
replace "CONFLUENT_CA_SECRET_NAME" "$(escape_for_perl "$CONFLUENT_CA_SECRET_NAME")"
replace "CONSUMER_GROUP_PREFIX" "$(escape_for_perl "$CONSUMER_GROUP_PREFIX")"
replace "CLUSTER_NAME" "$(escape_for_perl "$CLUSTER_NAME")"
replace "CLUSTER_ENVIRONMENT" "$(escape_for_perl "$CLUSTER_ENVIRONMENT")"
replace "CLUSTER_REGION" "$(escape_for_perl "$CLUSTER_REGION")"

if grep -RIn '{{[A-Z0-9_]*}}' "$out_dir"; then
  echo "unresolved placeholders remain" >&2
  exit 1
fi

echo "rendered namespace-scoped Alloy Kafka test manifests to: $out_dir"
echo "do not commit rendered files"
