#!/usr/bin/env bash

credential_secrets_to_prune() {
  local active_secret=$1
  local previous_secret=$2
  jq -r --arg active "$active_secret" --arg previous "$previous_secret" \
    '.items[].metadata.name | select(. != $active and . != $previous)'
}
