#!/usr/bin/env sh
set -eu

context=red
[ "$#" -gt 0 ] && context="$1"
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
require() { command -v "$1" >/dev/null || { echo "MISSING_COMMAND $1" >&2; exit 2; }; }
require kubectl
require jq

receipt="$(mktemp)"
result="$(mktemp)"
trap 'rm -f "$receipt" "$result"' EXIT

kubectl --context "$context" -n postgres-dab-mcp-poc rollout status deployment/postgres-dab-poc --timeout=90s
kubectl --context "$context" -n postgres-dab-mcp-poc rollout status deployment/postgres-compliance-mcp --timeout=90s
kubectl --context "$context" -n postgres-dab-mcp-poc wait --for=condition=complete job/postgres-dab-poc-seed --timeout=90s
echo "POSTGRES_SEED_JOB_COMPLETED_OK"
postgres_pod="$(kubectl --context "$context" -n postgres-dab-mcp-poc get pod -l app.kubernetes.io/name=postgres-dab-poc -o jsonpath='{.items[0].metadata.name}')"
kubectl --context "$context" -n postgres-dab-mcp-poc exec "$postgres_pod" -- sh -ec '
  PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U postgres -d governed_data -c "SELECT extname || '\''='\'' || extversion FROM pg_extension WHERE extname = '\''vector'\'';" | grep -q "^vector="
  PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U postgres -d governed_data -c "SELECT indexname FROM pg_indexes WHERE schemaname = '\''public'\'' AND tablename = '\''container_image_inventory'\'' AND indexname = '\''container_image_inventory_embedding_hnsw'\'';" | grep -qx container_image_inventory_embedding_hnsw
  PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U postgres -d governed_data -c "SELECT count(*) FROM public.v_namespace_image_summary WHERE namespace_name = '\''payments'\'' AND (critical_findings > 0 OR high_findings > 0);" | grep -qx 2
'
echo "PGVECTOR_EXTENSION_AND_INDEX_OK"
echo "POSTGRES_SYNTHETIC_KUBERNETES_QUERY_OK namespace=payments count=2"
# Avoid treating a transient controller rediscovery immediately after an MCP
# backend rollout as a product failure.
kubectl --context "$context" -n kagent wait --for=condition=Accepted remotemcpserver/postgres-kubernetes-inventory-readonly-mcp --timeout=3m
kubectl --context "$context" -n kagent wait --for=condition=Ready agent/postgres-kubernetes-inventory-lab-agent --timeout=3m
kubectl --context "$context" -n kagent get remotemcpserver postgres-kubernetes-inventory-readonly-mcp -o json | jq -e '
  (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
  and ([.status.discoveredTools[]?.name] | sort == ["get_image_risk_summary", "get_kubernetes_inventory_data_product_details", "get_namespace_container_images", "get_namespace_workload_summary"])
' >/dev/null
echo "REMOTE_MCP_DISCOVERY_OK"
kubectl --context "$context" -n kagent get agent postgres-kubernetes-inventory-lab-agent -o json | jq -e '
  (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
  and (.status.conditions[]? | select(.type == "Ready" and .status == "True"))
' >/dev/null
echo "KAGENT_AGENT_READY_OK"
"$root/../../scripts/kagent-a2a-invoke.sh" \
  --agent postgres-kubernetes-inventory-lab-agent --ns kagent --context "$context" --timeout 180 \
  --receipt-file "$receipt" --json \
  --text 'Which container images in the payments namespace have high or critical findings? Use the approved data tools and begin your final answer with POSTGRES_KUBERNETES_MCP_REPLY_OK.' \
  > "$result"
jq -e '.ok == true and (.text | test("POSTGRES_KUBERNETES_MCP_REPLY_OK")) and (.text | test("2"))' "$result" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.metadata.kagent_type == "function_response"
    and .data.name == "get_kubernetes_inventory_data_product_details"
    and .data.response.isError == false)] | length > 0' "$receipt" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.metadata.kagent_type == "function_response"
    and .data.name == "get_image_risk_summary"
    and .data.response.isError == false)] | length > 0' "$receipt" >/dev/null
echo "A2A_PARAMETERISED_TOOL_CALLS_OK"
echo "A2A_CONVERSATIONAL_RESPONSE_OK"
echo "VERIFY_PASS"
