#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"

kubectl --context "$HOST_CONTEXT" apply -k "$BUNDLE_DIR" >/dev/null
kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" delete remotemcpserver \
  kubernetes-mcp-fleet-direct --ignore-not-found >/dev/null

for attempt in $(seq 1 60); do
  backend=$(kubectl --context "$HOST_CONTEXT" -n "$AGENTGATEWAY_NAMESPACE" get \
    agentgatewaybackend "$MCP_NAME" \
    -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null || true)
  route=$(kubectl --context "$HOST_CONTEXT" -n "$AGENTGATEWAY_NAMESPACE" get \
    httproute "$MCP_NAME" \
    -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}' 2>/dev/null || true)
  gateway_tools=$(kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" get \
    remotemcpserver "$REMOTE_MCP_NAME" \
    -o jsonpath='{.status.discoveredTools[*].name}' 2>/dev/null || true)
  gateway_count=$(printf '%s\n' "$gateway_tools" | wc -w | tr -d ' ')
  gateway_tools_json=$(printf '%s' "$gateway_tools" | tr ' ' '\n' | \
    jq -Rsc 'split("\n") | map(select(length > 0)) | sort')
  if test "$backend" = "True" && test "$route" = "True" \
    && test "$gateway_count" -eq "$TOOL_COUNT" \
    && test "$gateway_tools_json" = "$EXPECTED_TOOLS_JSON"; then
    break
  fi
  if test "$attempt" -eq 60; then
    echo "timed out waiting for direct and gateway MCP discovery" >&2
    exit 1
  fi
  sleep 2
done

for attempt in $(seq 1 90); do
  accepted=$(kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" get agent \
    "$KAGENT_AGENT_NAME" \
    -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null || true)
  ready=$(kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" get agent \
    "$KAGENT_AGENT_NAME" \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
  if test "$accepted" = "True" && test "$ready" = "True"; then
    echo "REGISTER_OK gateway_tools=$TOOL_COUNT agent=Accepted,Ready direct_registration=absent"
    exit 0
  fi
  sleep 2
done

echo "timed out waiting for kagent Agent readiness" >&2
exit 1
