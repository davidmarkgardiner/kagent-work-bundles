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
  PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U postgres -d governed_data -c "SELECT indexname FROM pg_indexes WHERE schemaname = '\''public'\'' AND tablename = '\''compliance_findings'\'' AND indexname = '\''compliance_findings_embedding_hnsw'\'';" | grep -qx compliance_findings_embedding_hnsw
  PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U postgres -d governed_data -c "SELECT count(*) FROM public.v_compliance_exception_summary WHERE is_open = true AND severity_rank >= 3;" | grep -qx 2
'
echo "PGVECTOR_EXTENSION_AND_INDEX_OK"
echo "POSTGRES_SYNTHETIC_QUERY_OK count=2"
# Avoid treating a transient controller rediscovery immediately after an MCP
# backend rollout as a product failure.
kubectl --context "$context" -n kagent wait --for=condition=Accepted remotemcpserver/postgres-compliance-readonly-mcp --timeout=3m
kubectl --context "$context" -n kagent wait --for=condition=Ready agent/postgres-compliance-lab-agent --timeout=3m
kubectl --context "$context" -n kagent get remotemcpserver postgres-compliance-readonly-mcp -o json | jq -e '
  (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
  and ([.status.discoveredTools[]?.name] | sort == ["get_compliance_data_product_details", "get_open_high_severity_compliance_findings"])
' >/dev/null
echo "REMOTE_MCP_DISCOVERY_OK"
kubectl --context "$context" -n kagent get agent postgres-compliance-lab-agent -o json | jq -e '
  (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
  and (.status.conditions[]? | select(.type == "Ready" and .status == "True"))
' >/dev/null
echo "KAGENT_AGENT_READY_OK"
"$root/../../scripts/kagent-a2a-invoke.sh" \
  --agent postgres-compliance-lab-agent --ns kagent --context "$context" --timeout 180 \
  --receipt-file "$receipt" --json \
  --text 'How many open compliance findings are high severity or above? Use the approved data tools and begin your final answer with POSTGRES_MCP_REPLY_OK.' \
  > "$result"
jq -e '.ok == true and (.text | test("POSTGRES_MCP_REPLY_OK")) and (.text | test("2"))' "$result" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.metadata.kagent_type == "function_response"
    and .data.name == "get_compliance_data_product_details"
    and .data.response.isError == false)] | length > 0' "$receipt" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.metadata.kagent_type == "function_response"
    and .data.name == "get_open_high_severity_compliance_findings"
    and .data.response.isError == false)] | length > 0' "$receipt" >/dev/null
echo "A2A_TWO_TOOL_CALLS_OK"
echo "A2A_CONVERSATIONAL_RESPONSE_OK"
echo "VERIFY_PASS"
