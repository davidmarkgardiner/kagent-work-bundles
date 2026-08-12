#!/usr/bin/env sh
set -eu
context=red
[ "$#" -gt 0 ] && context="$1"
require() { command -v "$1" >/dev/null || { echo "MISSING_COMMAND $1"; exit 2; }; }
require kubectl
require jq
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-coordinator --timeout=90s
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-worker --timeout=90s
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-readonly-mcp --timeout=90s
kubectl --context "$context" -n data-mcp-poc wait --for=condition=complete job/trino-data-mcp-seed --timeout=90s
pod="$(kubectl --context "$context" -n data-mcp-poc get pod -l app.kubernetes.io/name=trino-readonly-mcp -o jsonpath='{.items[0].metadata.name}')"
output="$(kubectl --context "$context" -n data-mcp-poc exec "$pod" -- env PYTHONPATH=/tmp/site python -c 'from trino.dbapi import connect; c=connect(host="trino.data-mcp-poc.svc.cluster.local",port=8080,user="verify",catalog="memory",schema="default"); x=c.cursor(); x.execute("SELECT risk_band, overdue_accounts, overdue_balance FROM memory.default.account_risk ORDER BY risk_band"); print(x.fetchall())')"
echo "TRINO_SYNTHETIC_QUERY_OK $output"
kubectl --context "$context" -n kagent get remotemcpserver trino-readonly-data-mcp -o json | jq -e '.status.conditions[]? | select(.type=="Accepted" and .status=="True")' >/dev/null
kubectl --context "$context" -n kagent get remotemcpserver trino-readonly-data-mcp -o json | jq -e '[.status.discoveredTools[]?.name] | sort == ["get_data_product_details","get_overdue_risk_summary","search_data_products"]' >/dev/null
echo "REMOTE_MCP_DISCOVERY_OK"
kubectl --context "$context" -n kagent get agent trino-data-product-lab-agent -o json | jq -e '.status.conditions[]? | select(.type=="Accepted" and .status=="True")' >/dev/null
kubectl --context "$context" -n kagent get agent trino-data-product-lab-agent -o json | jq -e '.status.conditions[]? | select(.type=="Ready" and .status=="True")' >/dev/null
echo "KAGENT_AGENT_READY_OK"
echo "VERIFY_PASS"
