#!/usr/bin/env sh
set -eu
context=red
[ "$#" -gt 0 ] && context="$1"
require() { command -v "$1" >/dev/null || { echo "MISSING_COMMAND $1"; exit 2; }; }
require kubectl
require jq
repo_root="$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)"
receipt="$(mktemp)"
result="$(mktemp)"
trap 'rm -f "$receipt" "$result"' EXIT
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-coordinator --timeout=90s
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-worker --timeout=90s
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-readonly-mcp --timeout=90s
if kubectl --context "$context" -n data-mcp-poc get job/trino-data-mcp-seed >/dev/null 2>&1; then
  kubectl --context "$context" -n data-mcp-poc wait --for=condition=complete job/trino-data-mcp-seed --timeout=90s
  echo "TRINO_SEED_JOB_COMPLETED_OK"
else
  # A historical Job receipt can expire. The direct query below remains the
  # authoritative live-data gate; report the missing receipt rather than
  # pretending the table was just initialised.
  echo "TRINO_SEED_JOB_RECEIPT_EXPIRED"
fi
pod="$(kubectl --context "$context" -n data-mcp-poc get pod -l app.kubernetes.io/name=trino-readonly-mcp -o jsonpath='{.items[0].metadata.name}')"
output="$(kubectl --context "$context" -n data-mcp-poc exec "$pod" -- env PYTHONPATH=/tmp/site python -c 'from trino.dbapi import connect; c=connect(host="trino.data-mcp-poc.svc.cluster.local",port=8080,user="verify",catalog="memory",schema="default"); x=c.cursor(); x.execute("SELECT risk_band, overdue_accounts, overdue_balance FROM memory.default.account_risk ORDER BY risk_band"); print(x.fetchall())')"
echo "TRINO_SYNTHETIC_QUERY_OK $output"
kubectl --context "$context" -n kagent get remotemcpserver trino-readonly-data-mcp -o json | jq -e '.status.conditions[]? | select(.type=="Accepted" and .status=="True")' >/dev/null
kubectl --context "$context" -n kagent get remotemcpserver trino-readonly-data-mcp -o json | jq -e '[.status.discoveredTools[]?.name] | sort == ["get_data_product_details","get_overdue_risk_summary","search_data_products"]' >/dev/null
echo "REMOTE_MCP_DISCOVERY_OK"
kubectl --context "$context" -n kagent get agent trino-data-product-lab-agent -o json | jq -e '.status.conditions[]? | select(.type=="Accepted" and .status=="True")' >/dev/null
kubectl --context "$context" -n kagent get agent trino-data-product-lab-agent -o json | jq -e '.status.conditions[]? | select(.type=="Ready" and .status=="True")' >/dev/null
echo "KAGENT_AGENT_READY_OK"
"$repo_root/scripts/kagent-a2a-invoke.sh" \
  --agent trino-data-product-lab-agent --ns kagent --context "$context" --timeout 180 \
  --receipt-file "$receipt" --json \
  --text 'Use get_overdue_risk_summary. Start the answer with DATA_MCP_REPLY_OK and state the high, medium, and low account counts.' \
  > "$result"
jq -e '
  .agent == "trino-data-product-lab-agent"
  and .ok == true
  and (.text | test("DATA_MCP_REPLY_OK"))
  and (.text | test("high[^0-9]*3"; "i"))
  and (.text | test("medium[^0-9]*7"; "i"))
  and (.text | test("low[^0-9]*12"; "i"))
' "$result" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.kind == "data"
    and .metadata.kagent_type == "function_response"
    and .data.name == "get_overdue_risk_summary"
    and .data.response.isError == false)] | length > 0' "$receipt" >/dev/null
echo "A2A_TOOL_CALL_OK"
echo "A2A_CONVERSATIONAL_RESPONSE_OK"
echo "VERIFY_PASS"
