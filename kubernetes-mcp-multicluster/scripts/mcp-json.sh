#!/usr/bin/env bash

mcp_extract_jsonrpc_response() {
  local raw_response=$1
  local parsed sse_json

  if parsed=$(jq -cse \
    'map(select(.jsonrpc == "2.0" and .id == 1)) | if length == 1 then .[0] else error("expected one JSON-RPC response") end' \
    <<<"$raw_response" 2>/dev/null); then
    printf '%s\n' "$parsed"
    return 0
  fi

  sse_json=$(sed -n 's/^data: //p' <<<"$raw_response")
  parsed=$(jq -cse \
    'map(select(.jsonrpc == "2.0" and .id == 1)) | if length == 1 then .[0] else error("expected one SSE JSON-RPC response") end' \
    <<<"$sse_json") || {
      echo "unable to parse MCP response as JSON or SSE JSON-RPC" >&2
      return 1
    }
  printf '%s\n' "$parsed"
}

mcp_response_contains_marker() {
  local marker=$1
  jq -e --arg marker "$marker" \
    'any(.result.content[]?; ((.text? // "") | contains($marker)))'
}
