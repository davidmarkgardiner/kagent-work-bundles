#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
VECTOR_IMAGE="${VECTOR_IMAGE:-timberio/vector:0.45.0-debian}"
CONFIG_FILE="${ROOT_DIR}/observability/vector/tests/vector-example-test.yaml"
EXAMPLES_DIR="${ROOT_DIR}/observability/vector/examples"

run_vector() {
  docker run --rm -i \
    -v "${CONFIG_FILE}:/etc/vector/vector.yaml:ro" \
    "${VECTOR_IMAGE}" \
    --config /etc/vector/vector.yaml 2>/tmp/kagent-vector-example-test.err
}

assert_eq() {
  local actual="$1"
  local expected="$2"
  local label="$3"

  if [ "$actual" != "$expected" ]; then
    echo "FAIL ${label}: expected '${expected}', got '${actual}'" >&2
    exit 1
  fi
}

assert_json_field() {
  local json="$1"
  local jq_expr="$2"
  local expected="$3"
  local label="$4"
  local actual

  actual="$(printf '%s\n' "$json" | jq -r "$jq_expr")"
  assert_eq "$actual" "$expected" "$label"
}

run_one() {
  local name="$1"
  local fixture="$2"
  local output

  output="$(jq -c . "${EXAMPLES_DIR}/${fixture}" | run_vector)"
  if [ -z "$output" ]; then
    echo "FAIL ${name}: Vector emitted no output" >&2
    sed -n '1,160p' /tmp/kagent-vector-example-test.err >&2 || true
    exit 1
  fi

  printf '%s\n' "$output"
}

echo "Validating Vector config..."
docker run --rm \
  -v "${CONFIG_FILE}:/etc/vector/vector.yaml:ro" \
  "${VECTOR_IMAGE}" \
  validate --no-environment /etc/vector/vector.yaml >/dev/null

echo "Testing Alertmanager payload contract and routing..."
alertmanager_output="$(run_one alertmanager alertmanager-raw.json)"
assert_json_field "$alertmanager_output" '.schema_version' 'observability.triage.v1' 'alertmanager schema'
assert_json_field "$alertmanager_output" '.source' 'alertmanager' 'alertmanager source'
assert_json_field "$alertmanager_output" '.target_agent' 'aks-sre-triage-agent' 'alertmanager target_agent'
assert_json_field "$alertmanager_output" '.automation_allowed | tostring' 'false' 'alertmanager automation_allowed'
assert_json_field "$alertmanager_output" '.automation_policy' 'default-deny' 'alertmanager automation_policy'
assert_json_field "$alertmanager_output" '.dedupe_key' 'aks-dev-01:payments:checkout-api:PodCrashLooping' 'alertmanager dedupe_key'

echo "Testing Grafana-native payload contract and routing..."
grafana_output="$(run_one grafana grafana-native-raw.json)"
assert_json_field "$grafana_output" '.schema_version' 'observability.triage.v1' 'grafana schema'
assert_json_field "$grafana_output" '.source' 'grafana' 'grafana source'
assert_json_field "$grafana_output" '.event_type' 'grafana-alert' 'grafana event_type'
assert_json_field "$grafana_output" '.target_agent' 'aks-sre-triage-agent' 'grafana target_agent'
assert_json_field "$grafana_output" '.service' 'checkout-api' 'grafana service'
assert_json_field "$grafana_output" '.dedupe_key' 'unknown:payments:checkout-api:HighCPUUsage' 'grafana dedupe_key'

echo "Testing Alloy/Kubernetes event contract and platform routing..."
alloy_output="$(run_one alloy alloy-k8s-event-raw.json)"
assert_json_field "$alloy_output" '.schema_version' 'observability.triage.v1' 'alloy schema'
assert_json_field "$alloy_output" '.source' 'alloy' 'alloy source'
assert_json_field "$alloy_output" '.event_type' 'kubernetes-event' 'alloy event_type'
assert_json_field "$alloy_output" '.target_agent' 'platform-ops-agent' 'alloy target_agent'
assert_json_field "$alloy_output" '.pod' 'load-test-runner-6f8b7d8f9d-r7q2m' 'alloy pod'
assert_json_field "$alloy_output" '.dedupe_key' 'aks-dev-01:platform-tools:load-test-runner:FailedScheduling' 'alloy dedupe_key'

echo "Testing resolved-alert filtering..."
resolved_count="$(
  jq -c '.state = "ok"' "${EXAMPLES_DIR}/grafana-native-raw.json" | run_vector | wc -l | tr -d ' '
)"
assert_eq "$resolved_count" "0" "resolved alert should be filtered"

alertmanager_resolved_count="$(
  jq -c '.alertmanager.status = "resolved" | .alertmanager.alerts[0].status = "resolved"' "${EXAMPLES_DIR}/alertmanager-raw.json" | run_vector | wc -l | tr -d ' '
)"
assert_eq "$alertmanager_resolved_count" "0" "resolved alertmanager alert should be filtered"

echo "Testing duplicate suppression..."
dedupe_count="$(
  for _ in 1 2 3; do jq -c . "${EXAMPLES_DIR}/alertmanager-raw.json"; done | run_vector | wc -l | tr -d ' '
)"
assert_eq "$dedupe_count" "1" "duplicate alert suppression"

echo "PASS Vector example tests"
