#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$BUNDLE_DIR/../.." && pwd)"

required=(
  README.md
  GITLAB-TICKET.md
  VISUAL.html
  aks-mcp-values.yaml
  manifests/00-core.yaml
  manifests/01-cronworkflow.yaml
  manifests/02-agent.yaml
  manifests/03-argo-agent-router.yaml
  manifests/04-agentgateway.yaml
  kustomization.yaml
  scripts/refresh-fleet-kubeconfig.sh
  scripts/homelab-smoke.sh
  tests/test-refresh-script.sh
  evidence/management-smoke-receipt.json
  evidence/worker-smoke-receipt.json
)
for file_name in "${required[@]}"; do
  [[ -s "$BUNDLE_DIR/$file_name" ]] || { echo "missing required file: $file_name" >&2; exit 1; }
done

bash -n "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
bash -n "$BUNDLE_DIR/scripts/homelab-smoke.sh"
bash -n "$BUNDLE_DIR/tests/test-refresh-script.sh"
"$BUNDLE_DIR/tests/test-refresh-script.sh"
kubectl kustomize "$BUNDLE_DIR" >/dev/null
helm lint "$REPO_ROOT/platform/aks-mcp/chart" -f "$BUNDLE_DIR/aks-mcp-values.yaml" >/dev/null
rendered_chart="$(helm template aks-mcp "$REPO_ROOT/platform/aks-mcp/chart" \
  --namespace aks-mcp -f "$BUNDLE_DIR/aks-mcp-values.yaml")"
grep -q -- '--allowed-host' <<<"$rendered_chart"
grep -q 'name: validate-kubeconfig' <<<"$rendered_chart"
grep -q 'optional: false' <<<"$rendered_chart"
grep -q 'azure.workload.identity/use: "true"' <<<"$rendered_chart"
grep -q 'automountServiceAccountToken: false' <<<"$rendered_chart"
grep -q -- '--allow-namespaces' <<<"$rendered_chart"
grep -q '^kind: NetworkPolicy$' <<<"$rendered_chart"
grep -q 'appProtocol: "agentgateway.dev/mcp"' <<<"$rendered_chart"
if grep -q '^kind: ClusterRole$' <<<"$rendered_chart"; then
  echo "fleet shard values unexpectedly rendered management-cluster RBAC" >&2
  exit 1
fi
"$REPO_ROOT/scripts/public-safe-scan.sh" "$BUNDLE_DIR"

grep -q 'concurrencyPolicy: Forbid' "$BUNDLE_DIR/manifests/01-cronworkflow.yaml"
grep -q 'BLOCKED_UNKNOWN_CLUSTER' "$BUNDLE_DIR/manifests/03-argo-agent-router.yaml"
grep -q 'BLOCKED_UNKNOWN_NAMESPACE' "$BUNDLE_DIR/manifests/03-argo-agent-router.yaml"
grep -q 'allowedNamespaces' "$BUNDLE_DIR/manifests/00-core.yaml"
grep -q 'apiKeyAuthentication' "$BUNDLE_DIR/manifests/04-agentgateway.yaml"
grep -q 'mcp.tool.name == "call_kubectl"' "$BUNDLE_DIR/manifests/04-agentgateway.yaml"
grep -q 'headersFrom' "$BUNDLE_DIR/manifests/02-agent.yaml"
grep -q 'ai-gateway.agentgateway-system.svc.cluster.local' "$BUNDLE_DIR/manifests/02-agent.yaml"
grep -q -- '--context, --kubeconfig' "$BUNDLE_DIR/manifests/02-agent.yaml"
grep -q 'SHARD_DIR' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'replace -f' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'UNCHANGED' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'az login --service-principal' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q -- '--dry-run=server' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'ROLLOUT_MAX_PARALLEL' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'platform.example.com/kubeconfig-sha256' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'reconcile_rollout' "$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh"
grep -q 'function_response' "$BUNDLE_DIR/scripts/homelab-smoke.sh"
grep -q 'cleanup=\$cleanup_status' "$BUNDLE_DIR/scripts/homelab-smoke.sh"
jq -se '
  length == 2
  and ([.[].alias] | sort == ["management-smoke", "worker-smoke"])
  and ([.[].raw_receipt_sha256] | unique | length == 2)
  and all(.[];
    .remote_mcp_accepted == true
    and .discovered_tools == ["call_kubectl"]
    and .agent_ready == true
    and .task_state == "completed"
    and .function_responses == [{"name":"call_kubectl","explicit_error":false,"response_keys":["output"],"target_only_marker_matched":true}]
    and .final_artifact_marker_matched == true
    and .cleanup_verified == true
    and ((.raw_receipt_bytes | type) == "number")
    and .raw_receipt_bytes > 0
    and ((.raw_receipt_sha256 | type) == "string")
    and (.raw_receipt_sha256 | test("^[0-9a-f]{64}$"))
  )
' \
  "$BUNDLE_DIR/evidence/management-smoke-receipt.json" \
  "$BUNDLE_DIR/evidence/worker-smoke-receipt.json" >/dev/null

echo "PASS aks-mcp-fleet-kubeconfig-refresh bundle"
