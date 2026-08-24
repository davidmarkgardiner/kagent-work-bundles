#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"
# shellcheck source=mcp-json.sh
source "$BUNDLE_DIR/scripts/mcp-json.sh"
DIRECT_PORT=${DIRECT_PORT:-18080}
GATEWAY_PORT=${GATEWAY_PORT:-18081}

IFS=' ' read -r -a mappings <<< "$SMOKE_CONTEXTS_LIST"
test "${#mappings[@]}" -ge 2 || {
  echo "SMOKE_CONTEXTS must contain at least two alias=marker mappings" >&2
  exit 1
}

for mapping in "${mappings[@]}"; do
  alias_name=${mapping%%=*}
  marker=${mapping#*=}
  test -n "$alias_name" && test -n "$marker" && test "$alias_name" != "$marker" || {
    echo "invalid SMOKE_CONTEXTS mapping: $mapping" >&2
    exit 1
  }
done

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kubernetes-mcp-smoke.XXXXXX")
chmod 700 "$tmp_dir"
direct_log="$tmp_dir/direct-port-forward.log"
gateway_log="$tmp_dir/gateway-port-forward.log"

cleanup() {
  local status=$?
  if test "$status" -ne 0; then
    echo "smoke failed; port-forward diagnostics follow" >&2
    for file in "$direct_log" "$gateway_log"; do
      if test -s "$file"; then
        echo "== $(basename "$file") ==" >&2
        tail -20 "$file" >&2
      fi
    done
  fi
  if test -n "${direct_pid:-}"; then
    kill "$direct_pid" 2>/dev/null || true
    wait "$direct_pid" 2>/dev/null || true
  fi
  if test -n "${gateway_pid:-}"; then
    kill "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
  fi
  for file in "$direct_log" "$gateway_log"; do
    test ! -f "$file" || unlink "$file"
  done
  rmdir "$tmp_dir" 2>/dev/null || true
}
trap cleanup EXIT

kubectl --context "$HOST_CONTEXT" -n "$HOST_NAMESPACE" port-forward \
  service/kubernetes-mcp-fleet "$DIRECT_PORT:8080" >"$direct_log" 2>&1 &
direct_pid=$!
kubectl --context "$HOST_CONTEXT" -n "$AGENTGATEWAY_NAMESPACE" port-forward \
  service/"$AGENTGATEWAY_SERVICE" "$GATEWAY_PORT:80" >"$gateway_log" 2>&1 &
gateway_pid=$!

for attempt in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$DIRECT_PORT/healthz" >/dev/null \
    && curl --silent --output /dev/null \
      "http://127.0.0.1:$GATEWAY_PORT/mcp/kubernetes-mcp-fleet"; then
    break
  fi
  test "$attempt" -lt 30 || {
    echo "port-forward health check failed" >&2
    exit 1
  }
  sleep 1
done

request() {
  local target=$1
  local method=$2
  shift
  shift
  local params=${1:-'{}'}
  local payload response
  kill -0 "$direct_pid" 2>/dev/null || {
    echo "direct port-forward exited unexpectedly" >&2
    return 1
  }
  kill -0 "$gateway_pid" 2>/dev/null || {
    echo "agentgateway port-forward exited unexpectedly" >&2
    return 1
  }
  payload=$(jq -cn --arg method "$method" --argjson params "$params" \
    '{jsonrpc:"2.0",id:1,method:$method,params:$params}')
  response=$(curl --fail --silent --show-error \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    --request POST "$target" --data "$payload")
  mcp_extract_jsonrpc_response "$response"
}

check_context() {
  local label=$1
  local target=$2
  local selected=$3
  local expected_marker=$4
  local args params result other other_alias other_marker

  args=$(jq -cn --arg context "$selected" \
    '{apiVersion:"v1",kind:"Node",context:$context}')
  params=$(jq -cn --argjson args "$args" \
    '{name:"resources_list",arguments:$args}')
  result=$(request "$target" tools/call "$params")
  test "$(printf '%s' "$result" | jq -r '.result.isError // false')" = "false" || {
    echo "MCP tool returned an error: path=$label context=$selected" >&2
    return 1
  }
  printf '%s' "$result" | mcp_response_contains_marker "$expected_marker" >/dev/null || {
    echo "expected marker absent: path=$label context=$selected" >&2
    return 1
  }

  for other in "${mappings[@]}"; do
    other_alias=${other%%=*}
    test "$other_alias" = "$selected" && continue
    other_marker=${other#*=}
    if printf '%s' "$result" | mcp_response_contains_marker "$other_marker" >/dev/null; then
      echo "crossover detected: path=$label context=$selected" >&2
      exit 1
    fi
  done
}

check_path() {
  local label=$1
  local target=$2
  local listed actual mapping alias_name marker

  listed=$(request "$target" tools/list '{}')
  actual=$(printf '%s' "$listed" | jq -c '.result.tools | map(.name) | sort')
  test "$actual" = "$EXPECTED_TOOLS_JSON" || {
    echo "$label tool allowlist mismatch" >&2
    exit 1
  }
  test "$(printf '%s' "$listed" | jq '[.result.tools[] | select(.inputSchema.properties.context != null)] | length')" -eq "$TOOL_COUNT" || {
    echo "$label context-parameter coverage mismatch" >&2
    return 1
  }

  for mapping in "${mappings[@]}"; do
    alias_name=${mapping%%=*}
    marker=${mapping#*=}
    check_context "$label" "$target" "$alias_name" "$marker"
  done

  echo "MCP_PATH_OK path=$label tools=$TOOL_COUNT contexts=${#mappings[@]} crossover=0"
}

check_path direct "http://127.0.0.1:$DIRECT_PORT/mcp"
check_path agentgateway "http://127.0.0.1:$GATEWAY_PORT/mcp/kubernetes-mcp-fleet"

# Twenty alternating fresh sessions exercise the gateway path and context
# selection. They are sequential so every result can be checked independently.
for request_number in $(seq 1 20); do
  mapping=${mappings[$(((request_number - 1) % ${#mappings[@]}))]}
  alias_name=${mapping%%=*}
  marker=${mapping#*=}
  check_context agentgateway \
    "http://127.0.0.1:$GATEWAY_PORT/mcp/kubernetes-mcp-fleet" \
    "$alias_name" "$marker"
done

echo "ALTERNATING_SMOKE_OK requests=20 path=agentgateway crossover=0"
