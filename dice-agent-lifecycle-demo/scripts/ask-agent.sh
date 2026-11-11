# Source this file from Bash or Zsh after loading the private demo configuration.
ask_agent() {
  if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    printf '%s\n' 'Usage: ask_agent "PROMPT" [EXACT_EXPECTED_REPLY]' >&2
    return 2
  fi
  local variable
  for variable in DICE_DEMO_BUNDLE DEMO_AGENT_URL DEMO_CALLER_TOKEN_FILE DEMO_EVIDENCE_DIR; do
    if [ -z "$(printenv "$variable")" ]; then
      printf 'Export the required variable %s first.\n' "$variable" >&2
      return 2
    fi
  done
  if [ "$#" -eq 2 ]; then
    set -- --prompt "$1" --expect "$2"
  else
    set -- --prompt "$1"
  fi
  DICE_LAST_RECEIPT="${DEMO_EVIDENCE_DIR%/}/a2a-$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}.json"
  DICE_LAST_ANSWER="${DICE_LAST_RECEIPT%.json}.answer.txt"
  export DICE_LAST_RECEIPT DICE_LAST_ANSWER
  if (umask 077; set -C; python3 "$DICE_DEMO_BUNDLE/scripts/ask.py" \
      --url "$DEMO_AGENT_URL" --token-file "$DEMO_CALLER_TOKEN_FILE" \
      --receipt-file "$DICE_LAST_RECEIPT" "$@" > "$DICE_LAST_ANSWER"); then
    cat "$DICE_LAST_ANSWER"
  else
    local request_status=$?
    return "$request_status"
  fi
}
