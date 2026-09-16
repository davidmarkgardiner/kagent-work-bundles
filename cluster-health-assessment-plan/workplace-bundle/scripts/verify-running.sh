#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

WORKER_CONTEXT="${1:?usage: verify-running.sh WORKER_CONTEXT MANAGER_CONTEXT}"
MANAGER_CONTEXT="${2:?usage: verify-running.sh WORKER_CONTEXT MANAGER_CONTEXT}"
NAMESPACES_FILE="$BUNDLE_DIR/fox-mesh/namespaces.json"
EXPECTED="$(jq -r '.namespaces | length' "$NAMESPACES_FILE")"

for bin in kubectl jq curl; do
  command -v "$bin" >/dev/null 2>&1 || { echo "$bin is required" >&2; exit 1; }
done

assessor="system:serviceaccount:cluster-health-system:cluster-health-assessor"
bridge="system:serviceaccount:cluster-health-system:cluster-health-alert-bridge"
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$assessor" get nodes)" = yes
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$assessor" get secrets -n cluster-health-system)" = no
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$assessor" create pods -n cluster-health-system)" = no
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$bridge" get secrets -n cluster-health-system)" = no
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$bridge" list pods -A)" = no
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$bridge" create configmaps -n cluster-health-system)" = no
test "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$bridge" update configmap/cluster-health-alert-state -n cluster-health-system)" = yes

fox_json="$(kubectl --context "$WORKER_CONTEXT" -n cluster-health-system get deployment \
  -l app.kubernetes.io/part-of=cluster-health-fox-mesh -o json)"
jq -e --argjson expected "$EXPECTED" '
  (.items | length) == $expected and
  all(.items[]; (.spec.replicas == 1) and (.status.readyReplicas == 1) and
      (.status.updatedReplicas == 1) and (.status.availableReplicas == 1))
' <<<"$fox_json" >/dev/null

kubectl --context "$WORKER_CONTEXT" -n cluster-health-system rollout status \
  deployment/cluster-health-alert-bridge --timeout=120s >/dev/null

pointer="$(kubectl --context "$WORKER_CONTEXT" -n cluster-health-system get \
  configmap cluster-health-latest -o jsonpath='{.data.pointer\.json}')"
snapshot_name="$(jq -er '.snapshot' <<<"$pointer")"
snapshot="$(kubectl --context "$WORKER_CONTEXT" -n cluster-health-system get \
  configmap "$snapshot_name" -o jsonpath='{.data.snapshot\.json}')"
jq -e '
  (.cluster_id | type == "string" and length > 0) and
  (.source_generation | type == "string" and length > 0) and
  (.snapshot_seq | type == "number") and
  (.completed_at | fromdateiso8601 | (now - .) >= 0 and (now - .) <= 900) and
  (.display_score | type == "number" and . >= 0 and . <= 100) and
  (.gate.active | type == "boolean") and
  (.coverage.complete | type == "boolean")
' <<<"$snapshot" >/dev/null

missing_state=0
while IFS= read -r namespace; do
  if ! kubectl --context "$WORKER_CONTEXT" -n "$namespace" get \
    configmap fox-autonomous-monitor-state >/dev/null 2>&1; then
    echo "missing Fox state ConfigMap: $namespace/fox-autonomous-monitor-state" >&2
    missing_state=$((missing_state + 1))
  fi
done < <(jq -r '.namespaces[]' "$NAMESPACES_FILE")
test "$missing_state" -eq 0

kubectl --context "$MANAGER_CONTEXT" -n argo-events get \
  eventsource/cluster-health-kafka sensor/cluster-health-investigation \
  workflowtemplate/cluster-health-investigation >/dev/null
kubectl --context "$MANAGER_CONTEXT" -n kagent get \
  remotemcpserver >/dev/null

kubectl --context "$MANAGER_CONTEXT" -n kagent wait \
  --for=condition=Accepted agent/cluster-health-investigator --timeout=120s >/dev/null
kubectl --context "$MANAGER_CONTEXT" -n kagent wait \
  --for=condition=Ready agent/cluster-health-investigator --timeout=120s >/dev/null

verify_port="${KAGENT_VERIFY_PORT:-18083}"
kubectl --context "$MANAGER_CONTEXT" -n kagent port-forward \
  service/kagent-controller "${verify_port}:8083" >/dev/null 2>&1 &
port_forward_pid=$!
cleanup_port_forward() {
  kill "$port_forward_pid" 2>/dev/null || true
  wait "$port_forward_pid" 2>/dev/null || true
}
trap cleanup_port_forward EXIT
listed=false
for _ in $(seq 1 15); do
  if curl --fail --silent --max-time 2 "http://127.0.0.1:${verify_port}/api/agents" | \
    jq -e '.agents // .data // . | .[]? | select((.name // .agent.metadata.name // .metadata.name // "") | endswith("cluster-health-investigator"))' >/dev/null 2>&1; then
    listed=true
    break
  fi
  sleep 1
done
test "$listed" = true
cleanup_port_forward
trap - EXIT

echo "Running cluster-health deployment verification passed"
