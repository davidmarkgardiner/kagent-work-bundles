#!/usr/bin/env bash
# kagent-a2a-invoke.sh — invoke a kagent agent via the A2A JSON-RPC 2.0 API.
#
# One blessed implementation of the port-forward + curl + jq sequence that was
# previously copy-pasted across the skills and runbooks. It encodes the three
# documented A2A footguns so callers no longer have to remember them:
#
#   1. The invoke URL requires a trailing slash — omitting it returns 404.
#   2. Every message part must carry "kind":"text" alongside "text".
#   3. The session/chat API (/api/sessions, /api/chat) is broken on kagent
#      v0.8.0-beta4 — only the A2A protocol works. Never fall back to it.
#
# Usage:
#   scripts/kagent-a2a-invoke.sh --agent NAME --text 'PROMPT' [options]
#
# Options:
#   --agent NAME         Agent to invoke (required)
#   --text PROMPT        Message text (required unless --payload-file is given)
#   --payload-file FILE  JSON file containing a raw JSON-RPC "params" object,
#                        overriding the default message envelope
#   --ns NS              Agent namespace in the A2A path (default: kagent)
#   --sandbox            Invoke a SandboxAgent through /api/a2a-sandboxes/
#   --context-id ID      A2A context/session ID; reuse it to continue a task
#   --controller-ns NS   Namespace of svc/kagent-controller (default: kagent)
#   --context CTX        kubectl context for the port-forward
#   --local-port PORT    Local port for the port-forward (default: 8083)
#   --url URL            Controller base URL; skips the port-forward entirely
#                        (e.g. http://kagent-controller.kagent.svc.cluster.local:8083)
#   --timeout SECS       Max seconds to wait for the agent reply (default: 60)
#   --receipt-file FILE  Write the raw terminal JSON-RPC response to FILE
#   --raw                Print the full JSON-RPC response body
#   --json               Print {"agent","ok","text","elapsed_ms",...} instead of text
#   -h, --help           Show this help
#
# Exit codes:
#   0  success
#   2  agent not found (cross-checked against GET /api/agents)
#   3  transport or port-forward failure
#   4  timeout waiting for the agent reply
#   5  terminal response contained no agent text
set -euo pipefail

AGENT=""
TEXT=""
PAYLOAD_FILE=""
NS="kagent"
SANDBOX=0
CONTEXT_ID=""
CONTROLLER_NS="kagent"
CONTEXT=""
LOCAL_PORT="8083"
URL=""
TIMEOUT="60"
RECEIPT_FILE=""
RAW=0
JSON_OUT=0

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)        AGENT="$2"; shift 2 ;;
    --text)         TEXT="$2"; shift 2 ;;
    --payload-file) PAYLOAD_FILE="$2"; shift 2 ;;
    --ns)           NS="$2"; shift 2 ;;
    --sandbox)      SANDBOX=1; shift ;;
    --context-id)   CONTEXT_ID="$2"; shift 2 ;;
    --controller-ns) CONTROLLER_NS="$2"; shift 2 ;;
    --context)      CONTEXT="$2"; shift 2 ;;
    --local-port)   LOCAL_PORT="$2"; shift 2 ;;
    --url)          URL="$2"; shift 2 ;;
    --timeout)      TIMEOUT="$2"; shift 2 ;;
    --receipt-file) RECEIPT_FILE="$2"; shift 2 ;;
    --raw)          RAW=1; shift ;;
    --json)         JSON_OUT=1; shift ;;
    -h|--help)      usage 0 ;;
    *)              echo "kagent-a2a-invoke.sh: unknown option: $1" >&2; usage 3 >&2 ;;
  esac
done

if [[ -z "$AGENT" ]]; then
  echo "kagent-a2a-invoke.sh: --agent is required" >&2
  exit 3
fi
if [[ -z "$TEXT" && -z "$PAYLOAD_FILE" ]]; then
  echo "kagent-a2a-invoke.sh: --text or --payload-file is required" >&2
  exit 3
fi
if [[ -n "$PAYLOAD_FILE" && ! -f "$PAYLOAD_FILE" ]]; then
  echo "kagent-a2a-invoke.sh: payload file not found: $PAYLOAD_FILE" >&2
  exit 3
fi
for bin in curl jq; do
  command -v "$bin" >/dev/null 2>&1 || { echo "kagent-a2a-invoke.sh: $bin is required" >&2; exit 3; }
done

KUBECTL=(kubectl)
[[ -n "$CONTEXT" ]] && KUBECTL=(kubectl --context "$CONTEXT")

PF_PID=""
WORK_DIR="$(mktemp -d)"
cleanup() {
  if [[ -n "$PF_PID" ]]; then
    kill "$PF_PID" 2>/dev/null || true
    wait "$PF_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

if [[ -z "$URL" ]]; then
  command -v kubectl >/dev/null 2>&1 || { echo "kagent-a2a-invoke.sh: kubectl is required unless --url is given" >&2; exit 3; }
  "${KUBECTL[@]}" port-forward "svc/kagent-controller" "${LOCAL_PORT}:8083" -n "$CONTROLLER_NS" >/dev/null 2>"$WORK_DIR/pf.err" &
  PF_PID=$!
  URL="http://127.0.0.1:${LOCAL_PORT}"
  ready=0
  for _ in $(seq 1 15); do
    if ! kill -0 "$PF_PID" 2>/dev/null; then
      echo "kagent-a2a-invoke.sh: port-forward exited early (busy port? wrong context?):" >&2
      cat "$WORK_DIR/pf.err" >&2 || true
      echo "hint: pass --local-port to use a free port" >&2
      exit 3
    fi
    if curl -sf --max-time 2 "${URL}/api/agents" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    echo "kagent-a2a-invoke.sh: controller API not reachable at ${URL} after 15s" >&2
    exit 3
  fi
fi

BASE="${URL%/}"
# Footgun 1: the trailing slash below is REQUIRED — without it kagent returns 404.
A2A_PATH="api/a2a"
if [[ "$SANDBOX" -eq 1 ]]; then
  A2A_PATH="api/a2a-sandboxes"
fi
A2A_URL="${BASE}/${A2A_PATH}/${NS}/${AGENT}/"

REQ_ID="invoke-$$-$(date +%s)"
if [[ -z "$CONTEXT_ID" ]]; then
  CONTEXT_ID="context-${REQ_ID}"
fi
if [[ -n "$PAYLOAD_FILE" ]]; then
  PAYLOAD=$(jq -c --arg id "$REQ_ID" '{jsonrpc:"2.0", id:$id, method:"message/send", params:.}' "$PAYLOAD_FILE")
else
  # Footgun 2: the message needs a kind and unique messageId, and every part
  # needs kind:"text". Some A2A implementations accept less, but the full
  # envelope is required by the kagent-backed bridge fixtures.
  PAYLOAD=$(jq -cn --arg id "$REQ_ID" --arg text "$TEXT" \
    --arg context "$CONTEXT_ID" \
    '{jsonrpc:"2.0", id:$id, method:"message/send",
      params:{message:{kind:"message", messageId:$id, contextId:$context, role:"user",
                       parts:[{kind:"text", text:$text}]}}}')
fi

agent_listed() {
  curl -sf --max-time 10 "${BASE}/api/agents" 2>/dev/null | jq -e --arg name "$AGENT" '
    (.agents // .data // .) | .[]?
    | (.name // .agent.metadata.name // .metadata.name // "")
    | select(. == $name or endswith("/" + $name))' >/dev/null 2>&1
}

BODY_FILE="$WORK_DIR/body.json"
START_S=$(date +%s)
set +e
HTTP_CODE=$(curl -sS -o "$BODY_FILE" -w '%{http_code}' --max-time "$TIMEOUT" \
  -X POST "$A2A_URL" -H 'Content-Type: application/json' -d "$PAYLOAD" 2>"$WORK_DIR/curl.err")
CURL_RC=$?
set -e
END_S=$(date +%s)
ELAPSED_MS=$(( (END_S - START_S) * 1000 ))

if [[ "$CURL_RC" -eq 28 ]]; then
  echo "kagent-a2a-invoke.sh: timed out after ${TIMEOUT}s waiting for ${AGENT}" >&2
  exit 4
fi
if [[ "$CURL_RC" -ne 0 ]]; then
  echo "kagent-a2a-invoke.sh: transport failure calling ${A2A_URL}:" >&2
  cat "$WORK_DIR/curl.err" >&2 || true
  exit 3
fi

if [[ "$HTTP_CODE" == "404" ]]; then
  if ! agent_listed; then
    echo "kagent-a2a-invoke.sh: agent '${AGENT}' not found in ${BASE}/api/agents" >&2
    exit 2
  fi
  echo "kagent-a2a-invoke.sh: 404 from ${A2A_URL} although the agent is listed — check --ns or --sandbox" >&2
  exit 3
fi
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "kagent-a2a-invoke.sh: HTTP ${HTTP_CODE} from ${A2A_URL}" >&2
  head -c 2000 "$BODY_FILE" >&2 || true
  echo >&2
  exit 3
fi

if [[ -n "$RECEIPT_FILE" ]]; then
  receipt_parent="$(dirname "$RECEIPT_FILE")"
  if [[ ! -d "$receipt_parent" ]]; then
    echo "kagent-a2a-invoke.sh: receipt directory does not exist: ${receipt_parent}" >&2
    exit 3
  fi
  # Receipts can contain prompts and returned business data.  Do not create one
  # implicitly; when explicitly requested, save the exact controller response
  # with owner-only permissions for durable correlation and review.
  umask 077
  cp "$BODY_FILE" "$RECEIPT_FILE"
  chmod 600 "$RECEIPT_FILE"
fi

if jq -e '.error' "$BODY_FILE" >/dev/null 2>&1; then
  ERR_MSG=$(jq -r '.error.message // "unknown error"' "$BODY_FILE")
  echo "kagent-a2a-invoke.sh: JSON-RPC error: ${ERR_MSG}" >&2
  if echo "$ERR_MSG" | grep -qi 'not found' && ! agent_listed; then
    exit 2
  fi
  exit 3
fi

if [[ "$RAW" -eq 1 ]]; then
  cat "$BODY_FILE"
  echo
  exit 0
fi

# The normal terminal A2A shape has result.artifacts[].parts[].text.  Some
# controller/runtime paths persist a completed task but omit that projection
# from the immediate response, while retaining the terminal assistant message
# in result.history.  Use the final text-bearing agent history message only as
# a fallback; never treat tool-call arguments or function responses as a reply.
REPLY_SOURCE="artifact"
REPLY=$(jq -r '
  def text_parts:
    ([.parts[]? | select(.kind == "text" and (.text | type == "string")) | .text] | join("\n"))
    # Do not expose model reasoning tags in the caller-facing output.
    # The optional raw receipt remains the diagnostic source of truth.
    | gsub("(?s:<think>.*?</think>)[[:space:]]*"; "");
  ([.result.artifacts[]? | text_parts | select(length > 0)] | join("\n")) as $artifacts
  | if ($artifacts | length) > 0 then $artifacts
    else ([.result.history[]?
           | select(.role == "agent")
           | text_parts
           | select(length > 0)] | last // "")
    end
' "$BODY_FILE")
if [[ -z "$(jq -r '
  ([.result.artifacts[]?.parts[]? | select(.kind == "text" and (.text | type == "string")) | .text] | join("\n"))
  | gsub("(?s:<think>.*?</think>)[[:space:]]*"; "")
' "$BODY_FILE")" ]]; then
  REPLY_SOURCE="history-fallback"
fi
if [[ -z "$REPLY" ]]; then
  echo "kagent-a2a-invoke.sh: terminal response contained no agent text (state: $(jq -r '.result.status.state // "?"' "$BODY_FILE"))" >&2
  echo "hint: rerun with --raw or --receipt-file to inspect the full JSON-RPC response" >&2
  exit 5
fi

if [[ "$JSON_OUT" -eq 1 ]]; then
  jq -n --arg agent "$AGENT" --arg text "$REPLY" --arg reply_source "$REPLY_SOURCE" --argjson ms "$ELAPSED_MS" \
    '{agent:$agent, ok:true, text:$text, reply_source:$reply_source, elapsed_ms:$ms}'
else
  printf '%s\n' "$REPLY"
fi
