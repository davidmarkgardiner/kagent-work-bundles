#!/usr/bin/env bash

jwt_expiry_epoch() {
  local jwt=$1
  local payload padding
  payload=$(printf '%s' "$jwt" | cut -d. -f2)
  test -n "$payload" || return 1
  padding=$(( (4 - ${#payload} % 4) % 4 ))
  if test "$padding" -gt 0; then
    payload="$payload$(printf '=%.0s' $(seq 1 "$padding"))"
  fi
  printf '%s' "$payload" | tr '_-' '/+' | openssl base64 -d -A 2>/dev/null | \
    jq -er '.exp | select(type == "number")'
}
