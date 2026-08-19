#!/usr/bin/env sh
# Shared FastMCP password/UAMI live verifier.
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 KUBE_CONTEXT RECEIPT_FILE" >&2
  exit 2
fi

context=$1
receipt_file=$2
fastmcp_namespace=${FASTMCP_NAMESPACE:-fastmcp-entra-poc}
kagent_namespace=${KAGENT_NAMESPACE:-kagent}
root="$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd)"
result="$(mktemp)"
trap 'rm -f "$result"' EXIT

require() {
  command -v "$1" >/dev/null || {
    echo "MISSING_COMMAND $1" >&2
    exit 2
  }
}
require kubectl
require jq

# This verifier is intentionally read-only. Deployment and private placeholder
# rendering are separate, explicitly authorized operations.
kubectl --context "$context" -n "$fastmcp_namespace" \
  rollout status deployment/fastmcp-postgres-entra --timeout=3m

pod="$(kubectl --context "$context" -n "$fastmcp_namespace" get pod \
  -l app.kubernetes.io/name=fastmcp-postgres-entra \
  -o jsonpath='{.items[0].metadata.name}')"

kubectl --context "$context" -n "$fastmcp_namespace" exec "$pod" -- \
  python /app/verify_live.py

kubectl --context "$context" -n "$kagent_namespace" wait --for=condition=Accepted \
  remotemcpserver/fastmcp-postgres-entra --timeout=3m
kubectl --context "$context" -n "$kagent_namespace" wait --for=condition=Ready \
  agent/fastmcp-postgres-entra --timeout=3m

kubectl --context "$context" -n "$kagent_namespace" get remotemcpserver \
  fastmcp-postgres-entra -o json | jq -e '
    (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
    and ([.status.discoveredTools[]?.name] | sort == [
      "get_inventory_data_product_details",
      "get_namespace_count",
      "get_namespace_summary"
    ])
  ' >/dev/null
echo "REMOTE_MCP_EXACT_TOOL_DISCOVERY_OK"

kubectl --context "$context" -n "$kagent_namespace" get agent fastmcp-postgres-entra \
  -o json | jq -e '
    (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
    and (.status.conditions[]? | select(.type == "Ready" and .status == "True"))
  ' >/dev/null
echo "KAGENT_AGENT_READY_OK"

"$root/scripts/kagent-a2a-invoke.sh" \
  --agent fastmcp-postgres-entra --ns "$kagent_namespace" --context "$context" --timeout 180 \
  --receipt-file "$receipt_file" --json \
  --text 'How many namespaces are in the approved inventory? Use only the approved tools and begin the final answer with FASTMCP_A2A_OK.' \
  >"$result"

jq -e '.ok == true and (.text | test("FASTMCP_A2A_OK"))' "$result" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.metadata.kagent_type == "function_response"
    and .data.name == "get_inventory_data_product_details"
    and .data.response.isError == false)] | length > 0' "$receipt_file" >/dev/null
jq -e '[.result.history[]?.parts[]?
  | select(.metadata.kagent_type == "function_response"
    and .data.name == "get_namespace_count"
    and .data.response.isError == false)] | length > 0' "$receipt_file" >/dev/null

echo "FASTMCP_A2A_TOOL_CALLS_OK"
echo "FASTMCP_LIVE_VERIFY_PASS"
