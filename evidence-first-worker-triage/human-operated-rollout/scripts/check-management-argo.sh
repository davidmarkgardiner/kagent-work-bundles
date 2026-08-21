#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --values /path/to/private/values.env [--stage preflight|eventsource|workflow|all]" >&2
  exit 2
}

[[ "${1:-}" == "--values" && -n "${2:-}" ]] || usage
VALUES="$2"
STAGE="${4:-all}"
[[ -f "$VALUES" ]] || { echo "Values file not found: $VALUES" >&2; exit 2; }
case "$STAGE" in preflight|eventsource|workflow|all) ;; *) usage ;; esac

# Operator-selected values file is validated above.
set -a
# shellcheck disable=SC1090
source "$VALUES"
set +a
: "${MANAGEMENT_CONTEXT:?MANAGEMENT_CONTEXT is required}"
: "${MANAGEMENT_NAMESPACE:?MANAGEMENT_NAMESPACE is required}"
: "${EVENTBUS_NAME:?EVENTBUS_NAME is required}"
: "${EVENTSOURCE_NAME:?EVENTSOURCE_NAME is required}"
: "${SENSOR_NAME:?SENSOR_NAME is required}"
: "${WORKFLOW_TEMPLATE_NAME:?WORKFLOW_TEMPLATE_NAME is required}"
: "${EVENTSOURCE_LABEL:?EVENTSOURCE_LABEL is required}"

kc() { kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" "$@"; }
check_selected_image() {
  local selector="$1" expected="$2" actual
  [[ -z "$expected" ]] && return 0
  actual="$(kc get pods -l "$selector" -o jsonpath='{range .items[*].spec.containers[*]}{.image}{"\n"}{end}')"
  printf '%s\n' "$actual"
  grep -Fqx "$expected" <<<"$actual" || { echo "Expected selected-pod image not found: ${expected}" >&2; exit 1; }
  echo "IMAGE_OK selector=${selector} image=${expected}"
}

echo "== Context and Argo CRDs =="
kubectl --context "$MANAGEMENT_CONTEXT" config current-context
kc get namespace "$MANAGEMENT_NAMESPACE"
kubectl --context "$MANAGEMENT_CONTEXT" get crd eventsources.argoproj.io sensors.argoproj.io workflowtemplates.argoproj.io

if [[ "$STAGE" == "all" || "$STAGE" == "preflight" ]]; then
  echo "== Event bus and declared resources =="
  kc get eventbus "$EVENTBUS_NAME"
  kc get eventsource "$EVENTSOURCE_NAME" -o yaml
  kc get sensor "$SENSOR_NAME" -o yaml
  kc get workflowtemplate "$WORKFLOW_TEMPLATE_NAME" -o yaml
fi

if [[ "$STAGE" == "all" || "$STAGE" == "eventsource" ]]; then
  echo "== Kafka EventSource runtime =="
  kc get pods -l "$EVENTSOURCE_LABEL" -o wide
  check_selected_image "$EVENTSOURCE_LABEL" "${EVENTSOURCE_EXPECTED_IMAGE:-}"
  kc logs -l "$EVENTSOURCE_LABEL" --tail=150
  echo "== Scan for Kafka/broker errors (empty output is expected) =="
  kc logs -l "$EVENTSOURCE_LABEL" --tail=300 | rg -i 'group.authorization|group_authorization|topic.authorization|authentication|sasl|tls|certificate|kafka.*error' || true
fi

if [[ "$STAGE" == "all" || "$STAGE" == "workflow" ]]; then
  echo "== Sensor-triggered workflow evidence =="
  kc get workflows --sort-by=.metadata.creationTimestamp
  kc get events --sort-by=.lastTimestamp | tail -40 || true
fi

echo "MANAGEMENT_CHECK_COMPLETE: confirm the EventSource group advances in Confluent and a sensor-triggered workflow exists before proceeding."
