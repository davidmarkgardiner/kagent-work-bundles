#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"

kubectl --context "$HOST_CONTEXT" apply -k "$BUNDLE_DIR" >/dev/null

for attempt in $(seq 1 60); do
  backend=$(kubectl --context "$HOST_CONTEXT" -n "$AGENTGATEWAY_NAMESPACE" get \
    agentgatewaybackend kubernetes-mcp-fleet \
    -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null || true)
  route=$(kubectl --context "$HOST_CONTEXT" -n "$AGENTGATEWAY_NAMESPACE" get \
    httproute kubernetes-mcp-fleet \
    -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}' 2>/dev/null || true)
  direct_tools=$(kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" get \
    remotemcpserver kubernetes-mcp-fleet-direct \
    -o jsonpath='{.status.discoveredTools[*].name}' 2>/dev/null || true)
  gateway_tools=$(kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" get \
    remotemcpserver kubernetes-mcp-fleet-gateway \
    -o jsonpath='{.status.discoveredTools[*].name}' 2>/dev/null || true)
  direct_count=$(printf '%s\n' "$direct_tools" | wc -w | tr -d ' ')
  gateway_count=$(printf '%s\n' "$gateway_tools" | wc -w | tr -d ' ')
  if test "$backend" = "True" && test "$route" = "True" \
    && test "$direct_count" -eq 8 \
    && test "$gateway_count" -eq 8; then
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
    kubernetes-mcp-fleet-agent \
    -o jsonpath='{.status.conditions[?(@.type=="Accepted")].status}' 2>/dev/null || true)
  ready=$(kubectl --context "$HOST_CONTEXT" -n "$KAGENT_NAMESPACE" get agent \
    kubernetes-mcp-fleet-agent \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
  if test "$accepted" = "True" && test "$ready" = "True"; then
    echo "REGISTER_OK direct_tools=8 gateway_tools=8 agent=Accepted,Ready"
    exit 0
  fi
  sleep 2
done

echo "timed out waiting for kagent Agent readiness" >&2
exit 1
