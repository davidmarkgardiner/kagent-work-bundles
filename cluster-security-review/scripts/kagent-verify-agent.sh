#!/usr/bin/env bash
# kagent-verify-agent.sh — verify a kagent Agent is genuinely ready to serve.
#
# Replaces the 4-command verify blocks narrated in the deployment docs with a
# single call that gates on, in order:
#   1. Agent CR condition Accepted=True
#   2. Agent CR condition Ready=True
#   3. Agent listed by the controller API (GET /api/agents)
#   4. Optional A2A smoke reply (via scripts/kagent-a2a-invoke.sh)
#
# Usage:
#   scripts/kagent-verify-agent.sh --agent NAME [options]
#
# Options:
#   --agent NAME       Agent to verify (required)
#   --ns NS            Namespace of the Agent CR (default: kagent)
#   --controller-ns NS Namespace of svc/kagent-controller (default: kagent)
#   --context CTX      kubectl context
#   --timeout SECS     Max seconds to wait for Accepted+Ready (default: 120)
#   --local-port PORT  Local port for the controller port-forward (default: 18083)
#   --smoke PROMPT     After readiness, invoke the agent and require a reply
#   --json             Print a JSON summary instead of PASS/FAIL lines
#   -h, --help         Show this help
#
# Exit codes:
#   0  all gates passed
#   2  not Accepted within timeout
#   3  Accepted but not Ready within timeout (condition message printed)
#   4  controller API does not list the agent
#   5  smoke invoke failed or returned an empty reply
#   6  controller transport or port-forward failure
#   7  Agent generation/readiness changed after the readiness gate
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

AGENT=""
NS="kagent"
CONTROLLER_NS="kagent"
CONTEXT=""
TIMEOUT="120"
LOCAL_PORT="18083"
SMOKE=""
JSON_OUT=0

usage() {
  sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)         AGENT="$2"; shift 2 ;;
    --ns)            NS="$2"; shift 2 ;;
    --controller-ns) CONTROLLER_NS="$2"; shift 2 ;;
    --context)       CONTEXT="$2"; shift 2 ;;
    --timeout)       TIMEOUT="$2"; shift 2 ;;
    --local-port)    LOCAL_PORT="$2"; shift 2 ;;
    --smoke)         SMOKE="$2"; shift 2 ;;
    --json)          JSON_OUT=1; shift ;;
    -h|--help)       usage 0 ;;
    *)               echo "kagent-verify-agent.sh: unknown option: $1" >&2; usage 1 >&2 ;;
  esac
done

if [[ -z "$AGENT" ]]; then
  echo "kagent-verify-agent.sh: --agent is required" >&2
  exit 1
fi
for bin in kubectl curl jq; do
  command -v "$bin" >/dev/null 2>&1 || { echo "kagent-verify-agent.sh: $bin is required" >&2; exit 1; }
done

KUBECTL=(kubectl)
[[ -n "$CONTEXT" ]] && KUBECTL=(kubectl --context "$CONTEXT")

ACCEPTED=false
READY=false
API_LISTED=false
SMOKE_OK=""

report() { # status text
  if [[ "$JSON_OUT" -eq 0 ]]; then
    printf '%s %s\n' "$1" "$2"
  fi
}

finish() { # exit_code
  if [[ "$JSON_OUT" -eq 1 ]]; then
    jq -n --arg agent "$AGENT" --arg ns "$NS" \
      --argjson accepted "$ACCEPTED" --argjson ready "$READY" \
      --argjson api_listed "$API_LISTED" --arg smoke "${SMOKE_OK:-skipped}" \
      --argjson code "$1" \
      '{agent:$agent, ns:$ns, accepted:$accepted, ready:$ready,
        api_listed:$api_listed, smoke:$smoke, exit_code:$code}'
  fi
  exit "$1"
}

WORK_DIR="$(mktemp -d)"
PF_PID=""
cleanup() {
  if [[ -n "$PF_PID" ]]; then
    kill "$PF_PID" 2>/dev/null || true
    wait "$PF_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

snapshot() {
  "${KUBECTL[@]}" get agent "$AGENT" -n "$NS" -o json > "$WORK_DIR/agent.json" 2> "$WORK_DIR/get.err"
}

current_condition() {
  jq -e --arg condition "$1" '
    .metadata.generation as $generation
    | .status.observedGeneration as $top
    | ($generation | type == "number") and
      any(.status.conditions[]?;
        .type == $condition and .status == "True"
        and ((.observedGeneration // $top) | type == "number")
        and (.observedGeneration // $top) == $generation)
  ' "$WORK_DIR/agent.json" >/dev/null 2>&1
}

generation_evidence() {
  jq -e '
    . as $doc | .metadata.generation as $generation | .status.observedGeneration as $top
    | ($generation | type == "number")
      and all(["Accepted", "Ready"][];
        . as $condition | any($doc.status.conditions[]?;
          .type == $condition and ((.observedGeneration // $top) | type == "number")))
  ' "$WORK_DIR/agent.json" >/dev/null 2>&1
}

DEADLINE=$(( $(date +%s) + TIMEOUT ))
GENERATION=""
while true; do
  if ! snapshot; then
    cat "$WORK_DIR/get.err" >&2
    report "FAIL" "accepted — cannot read Agent JSON"
    finish 2
  fi
  if current_condition Accepted; then
    ACCEPTED=true
  else
    ACCEPTED=false
  fi
  if [[ "$ACCEPTED" == true ]] && current_condition Ready; then
    READY=true
    GENERATION=$(jq -r '.metadata.generation' "$WORK_DIR/agent.json")
    break
  fi
  if [[ $(date +%s) -ge $DEADLINE ]]; then
    if ! generation_evidence; then
      echo "kagent-verify-agent.sh: generation evidence unavailable: numeric metadata.generation and observedGeneration for Accepted/Ready (per condition or status) are required; readiness unverified" >&2
      report "FAIL" "accepted/ready — generation evidence unavailable"
      finish 2
    fi
    detail=$(jq -c '{generation:.metadata.generation,observedGeneration:.status.observedGeneration,conditions:.status.conditions}' "$WORK_DIR/agent.json")
    echo "kagent-verify-agent.sh: current-generation readiness not established: $detail" >&2
    if [[ "$ACCEPTED" == true ]]; then
      report "FAIL" "ready — no True Ready condition for current generation"
      finish 3
    fi
    report "FAIL" "accepted — no True Accepted condition for current generation"
    finish 2
  fi
  sleep 1
done
report "PASS" "accepted generation=${GENERATION}"
report "PASS" "ready generation=${GENERATION}"

# Gate 3: controller transport, then listing, while preserving the checked generation.
"${KUBECTL[@]}" port-forward svc/kagent-controller "${LOCAL_PORT}:8083" -n "$CONTROLLER_NS" >/dev/null 2> "$WORK_DIR/pf.err" &
PF_PID=$!
TRANSPORT=false
for _ in $(seq 1 15); do
  if ! kill -0 "$PF_PID" 2>/dev/null; then
    echo "kagent-verify-agent.sh: controller port-forward exited:" >&2
    cat "$WORK_DIR/pf.err" >&2
    report "FAIL" "controller transport — port-forward exited"
    finish 6
  fi
  if curl -sf --max-time 2 "http://127.0.0.1:${LOCAL_PORT}/api/agents" > "$WORK_DIR/agents.json" 2> "$WORK_DIR/curl.err"; then
    TRANSPORT=true
    break
  fi
  sleep 1
done
if [[ "$TRANSPORT" != true ]]; then
  echo "kagent-verify-agent.sh: controller API transport unavailable after 15s" >&2
  cat "$WORK_DIR/pf.err" "$WORK_DIR/curl.err" >&2
  report "FAIL" "controller transport — API unreachable"
  finish 6
fi
if ! snapshot || [[ "$(jq -r '.metadata.generation' "$WORK_DIR/agent.json")" != "$GENERATION" ]] \
    || ! current_condition Accepted || ! current_condition Ready; then
  ACCEPTED=false
  READY=false
  echo "kagent-verify-agent.sh: Agent generation/readiness changed after generation=${GENERATION}; rerun verification" >&2
  report "FAIL" "accepted/ready — generation or readiness changed"
  finish 7
fi
if ! jq -e --arg name "$AGENT" '
    (.agents // .data // .) | .[]?
    | (.name // .agent.metadata.name // .metadata.name // "")
    | select(. == $name or endswith("/" + $name))' "$WORK_DIR/agents.json" >/dev/null 2>&1; then
  report "FAIL" "api-listed — agent absent from GET /api/agents (transport succeeded)"
  finish 4
fi
API_LISTED=true
report "PASS" "api-listed generation=${GENERATION}"
kill "$PF_PID" 2>/dev/null || true
wait "$PF_PID" 2>/dev/null || true
PF_PID=""

# Gate 4: optional A2A smoke
if [[ -n "$SMOKE" ]]; then
  INVOKE=("$SCRIPT_DIR/kagent-a2a-invoke.sh" --agent "$AGENT" --ns "$NS" \
    --controller-ns "$CONTROLLER_NS" --local-port "$LOCAL_PORT" --text "$SMOKE")
  [[ -n "$CONTEXT" ]] && INVOKE+=(--context "$CONTEXT")
  if "${INVOKE[@]}" >/dev/null; then
    SMOKE_OK=true
    report "PASS" "smoke-reply"
  else
    SMOKE_OK=false
    report "FAIL" "smoke-reply"
    finish 5
  fi
fi

finish 0
