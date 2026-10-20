#!/usr/bin/env bash
set -euo pipefail
bundle_dir=$(cd "$(dirname "$0")/.." && pwd)
context=${KUBE_CONTEXT:?Set KUBE_CONTEXT explicitly}
namespace=${FLOW_NAMESPACE:-agent-flow-demo}
values=${1:?Pass the reviewed Helm values file}
python3 "$bundle_dir/scripts/preflight.py" --context "$context" --namespace "$namespace" --values "$values"
integration_mode=$(python3 -c 'import sys,yaml;print(yaml.safe_load(open(sys.argv[1])).get("integration",{}).get("mode","bundled"))' "$values")
if [[ "$integration_mode" != existing ]]; then
  : "${FLOW_STATE_DIR:?Set FLOW_STATE_DIR outside the bundle for private rollback state}"
fi
helm --kube-context "$context" upgrade --install flow-demo "$bundle_dir/deploy/chart" -n "$namespace" --create-namespace -f "$values" --wait --timeout 5m
agent_namespace=$(python3 -c 'import sys,yaml;print(yaml.safe_load(open(sys.argv[1])).get("agentNamespace","kagent"))' "$values")
if [[ "$integration_mode" == existing ]]; then
  agent_name=$(python3 -c 'import sys,yaml;print(yaml.safe_load(open(sys.argv[1]))["integration"]["existingAgent"])' "$values")
  kubectl --context "$context" -n "$agent_namespace" wait --for=condition=Ready "agent/$agent_name" --timeout=180s
  echo "Existing-agent mode leaves platform telemetry unchanged. Configure the approved collector fan-out before verifying live flows."
  exit 0
fi
state_dir=${FLOW_STATE_DIR:?Set FLOW_STATE_DIR outside the bundle for private rollback state}
telemetry_args=(--context "$context" --namespace "$namespace" --agent-namespace "$agent_namespace" --state-dir "$state_dir")
[[ -z "${FLOW_SUBSTRATE_CHART:-}" ]] || telemetry_args+=(--substrate-chart "$FLOW_SUBSTRATE_CHART")
[[ -z "${FLOW_KAGENT_CHART:-}" ]] || telemetry_args+=(--kagent-chart "$FLOW_KAGENT_CHART")
python3 "$bundle_dir/scripts/platform-telemetry.py" "${telemetry_args[@]}"
kubectl --context "$context" -n "$agent_namespace" wait --for=condition=Ready agent/flow-demo-agent --timeout=180s
