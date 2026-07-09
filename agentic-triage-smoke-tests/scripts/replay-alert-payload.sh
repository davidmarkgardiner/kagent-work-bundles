#!/usr/bin/env bash
set -euo pipefail

KUBE_CONTEXT="${KUBE_CONTEXT:-}"
ARGO_EVENTS_NAMESPACE="${ARGO_EVENTS_NAMESPACE:-argo-events}"
EVENTSOURCE_SERVICE="${EVENTSOURCE_SERVICE:-smart-triage-alertmanager-eventsource-svc}"
LOCAL_PORT="${LOCAL_PORT:-12000}"
PAYLOAD_FILE="${1:-}"

if [[ -z "$PAYLOAD_FILE" ]]; then
  echo "usage: $0 <alertmanager-payload.json>" >&2
  exit 2
fi

if [[ ! -f "$PAYLOAD_FILE" ]]; then
  echo "payload file not found: $PAYLOAD_FILE" >&2
  exit 2
fi

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

need kubectl
need curl

KUBECTL=(kubectl)
if [[ -n "$KUBE_CONTEXT" ]]; then
  KUBECTL+=(--context "$KUBE_CONTEXT")
fi

pf_log="$(mktemp)"
cleanup() {
  if [[ -n "${PF_PID:-}" ]]; then
    kill "$PF_PID" >/dev/null 2>&1 || true
    wait "$PF_PID" >/dev/null 2>&1 || true
  fi
  rm -f "$pf_log"
}
trap cleanup EXIT

echo "== Smart triage Alertmanager payload replay =="
echo "namespace: $ARGO_EVENTS_NAMESPACE"
echo "service: $EVENTSOURCE_SERVICE"
echo "payload: $PAYLOAD_FILE"

"${KUBECTL[@]}" -n "$ARGO_EVENTS_NAMESPACE" get svc "$EVENTSOURCE_SERVICE" >/dev/null
"${KUBECTL[@]}" -n "$ARGO_EVENTS_NAMESPACE" port-forward "svc/$EVENTSOURCE_SERVICE" "$LOCAL_PORT:12000" >"$pf_log" 2>&1 &
PF_PID="$!"

for _ in $(seq 1 30); do
  if grep -q "Forwarding from" "$pf_log"; then
    break
  fi
  if ! kill -0 "$PF_PID" >/dev/null 2>&1; then
    cat "$pf_log" >&2
    exit 1
  fi
  sleep 1
done

if ! grep -q "Forwarding from" "$pf_log"; then
  echo "port-forward did not become ready" >&2
  cat "$pf_log" >&2
  exit 1
fi

curl -sS -X POST "http://127.0.0.1:$LOCAL_PORT/alerts" \
  -H "Content-Type: application/json" \
  --data-binary @"$PAYLOAD_FILE"
echo
echo "ALERT_REPLAYED: yes"
