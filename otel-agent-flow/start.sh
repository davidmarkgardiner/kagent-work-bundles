#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
context="${FLOW_CONTEXT:-kind-agent-cage-health}"
if [[ "$context" != kind-* ]]; then
  echo "This launcher is scoped to a local kind context." >&2
  exit 1
fi
k=(kubectl --context "$context" --request-timeout=30s)
"${k[@]}" create namespace otel-agent-flow --dry-run=client -o yaml | "${k[@]}" apply -f -
"${k[@]}" apply --dry-run=server -f manifests.yaml >/dev/null
"${k[@]}" -n otel-agent-flow create configmap flow-app --from-file=backend.py --from-file=telemetry.py --dry-run=client -o yaml | "${k[@]}" apply -f -
"${k[@]}" -n otel-agent-flow create configmap flow-ui --from-file=ui/ --dry-run=client -o yaml | "${k[@]}" apply -f -
"${k[@]}" apply -f manifests.yaml
"${k[@]}" -n otel-agent-flow rollout restart deployment/flow-dashboard deployment/flow-collector
"${k[@]}" -n otel-agent-flow rollout status deployment/flow-dashboard --timeout=120s
"${k[@]}" -n otel-agent-flow rollout status deployment/flow-collector --timeout=120s
bash ../../scripts/kagent-verify-agent.sh --context "$context" --agent otel-flow-reader --timeout 180 --local-port 18783
echo "Open http://127.0.0.1:8787"
exec kubectl --context "$context" -n otel-agent-flow port-forward --address 127.0.0.1 service/flow-dashboard 8787:8787
