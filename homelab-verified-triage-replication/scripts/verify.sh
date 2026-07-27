#!/usr/bin/env bash
# Read-only health + wiring check for the evidence-first triage path.
# Mutates nothing. Prints a PASS/FAIL line per component and exits non-zero if
# any component is unhealthy.
#
#   bash scripts/verify.sh --context <kubectl-context>
set -uo pipefail

CONTEXT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --context) CONTEXT="${2:?--context needs a value}"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$CONTEXT" ] || { echo "ERROR: --context is required" >&2; exit 2; }
K="kubectl --context $CONTEXT"

rc=0
pass() { printf '  PASS  %s\n' "$*"; }
fail() { printf '  FAIL  %s\n' "$*"; rc=1; }
info() { printf '  ..    %s\n' "$*"; }

echo "== 1. Worker collection (Alloy) =="
if [ "$($K -n monitoring get deploy alloy-vector-triage -o jsonpath='{.status.readyReplicas}' 2>/dev/null)" = "1" ]; then
  pass "alloy-vector-triage ready"
else
  fail "alloy-vector-triage not ready"
fi
if $K -n monitoring logs -l app=alloy-vector-triage --tail=200 2>/dev/null | grep -qi 'level=error'; then
  fail "alloy is logging errors: $($K -n monitoring logs -l app=alloy-vector-triage --tail=200 2>/dev/null | grep -i 'level=error' | tail -1)"
else
  pass "alloy log clean"
fi

echo
echo "== 2. Worker normalisation + produce (Vector) =="
if [ "$($K -n argo-events get deploy vector-telemetry-triage -o jsonpath='{.status.readyReplicas}' 2>/dev/null)" = "1" ]; then
  pass "vector-telemetry-triage ready"
else
  fail "vector-telemetry-triage not ready"
fi
if $K -n argo-events logs -l app=vector-telemetry-triage --tail=200 2>/dev/null | grep -qiE '\bERROR\b|Healthcheck failed'; then
  fail "vector is logging errors / failed healthcheck"
else
  pass "vector log clean, healthchecks passed"
fi

# Pipeline counters. These are the honest answer to "is dedup working and are
# drops metered rather than silent".
METRICS="$($K -n argo-events run vector-verify-$RANDOM --rm -i --restart=Never --quiet \
  --image=badouralix/curl-jq:alpine -- \
  sh -c 'curl -s --max-time 20 http://vector-telemetry-triage.argo-events:9598/metrics' 2>/dev/null)"
if printf '%s' "$METRICS" | grep -q vector_component_sent_events_total; then
  pass "vector metrics endpoint reachable (:9598)"
  m() { printf '%s' "$METRICS" | grep -E "$1" | grep -oE '[0-9]+ [0-9]+$' | awk '{print $1}' | head -1; }
  echo "        received   alloy_otlp             $(m 'component_sent_events_total.*component_id="alloy_otlp".*output="logs"')"
  echo "        passed     incident_signals       $(m 'component_sent_events_total.*component_id="incident_signals"')"
  echo "        DROPPED    incident_signals       $(m 'component_discarded_events_total.*component_id="incident_signals"')   <- policy filter, metered not silent"
  echo "        DROPPED    suppress_exact_repeats $(m 'component_discarded_events_total.*component_id="suppress_exact_repeats"')   <- repeat suppression"
  echo "        produced   kafka                  $(m 'component_sent_events_total.*component_id="kafka"')"
else
  fail "vector metrics endpoint not reachable on :9598"
fi

echo
echo "== 3. Management ingest (Kafka EventSource) =="
ES_POD="$($K -n argo-events get pods -l eventsource-name=red-telemetry-triage-kafka -o name 2>/dev/null | head -1)"
if [ -n "$ES_POD" ]; then
  pass "eventsource pod running ($ES_POD)"
  # Read the WHOLE log, not a tail: on a busy pipeline the one-off startup line
  # scrolls out of any fixed tail window and the check false-negatives.
  ES_LOG="$($K -n argo-events logs "$ES_POD" --tail=-1 2>/dev/null)"
  if printf '%s' "$ES_LOG" | grep -q 'consumer group up and running'; then
    pass "Sarama consumer group connected to Kafka"
  elif printf '%s' "$ES_LOG" | grep -q 'Succeeded to publish an event'; then
    pass "consumer connected (startup line rotated out; publishes observed)"
  else
    fail "eventsource never reported a connected consumer group — check SASL creds / topic / ACLs"
  fi
  if printf '%s' "$ES_LOG" | grep -qiE 'kafka.*(error|failed)|SASL|authentication failed'; then
    fail "eventsource log contains Kafka errors: $(printf '%s' "$ES_LOG" | grep -iE 'kafka.*(error|failed)|SASL|authentication failed' | tail -1)"
  else
    pass "no Kafka errors in eventsource log"
  fi
  info "events published to eventbus in retained log: $(printf '%s' "$ES_LOG" | grep -c 'Succeeded to publish an event')"
else
  fail "eventsource pod not found"
fi

echo
echo "== 4. Management routing (Sensors) =="
for s in red-log-triage red-event-triage; do
  p="$($K -n argo-events get pods -l "sensor-name=$s" -o name 2>/dev/null | head -1)"
  if [ -z "$p" ]; then
    fail "sensor $s has no pod"
    continue
  fi
  ready="$($K -n argo-events get "$p" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null)"
  # Same rotation problem as the eventsource: 'Sensor started' is a one-off line.
  # Treat container readiness as the primary signal and the log as corroboration.
  S_LOG="$($K -n argo-events logs "$p" --tail=-1 2>/dev/null)"
  if [ "$ready" = "true" ] && printf '%s' "$S_LOG" | grep -q 'Sensor started'; then
    pass "sensor $s started and subscribed"
  elif [ "$ready" = "true" ]; then
    pass "sensor $s pod ready (startup line rotated out)"
  else
    fail "sensor $s pod not ready"
  fi
  if printf '%s' "$S_LOG" | grep -q '"level":"error"'; then
    fail "sensor $s logging errors: $(printf '%s' "$S_LOG" | grep '"level":"error"' | tail -1 | cut -c1-200)"
  fi
done

echo
echo "== 5. Backend (WorkflowTemplate, semaphore, agent) =="
if $K -n argo-events get workflowtemplate red-agentic-triage >/dev/null 2>&1; then
  pass "workflowtemplate red-agentic-triage present"
  pod_gc="$($K -n argo-events get workflowtemplate red-agentic-triage -o jsonpath='{.spec.podGC.strategy}' 2>/dev/null)"
  ttl_success="$($K -n argo-events get workflowtemplate red-agentic-triage -o jsonpath='{.spec.ttlStrategy.secondsAfterSuccess}' 2>/dev/null)"
  ttl_failure="$($K -n argo-events get workflowtemplate red-agentic-triage -o jsonpath='{.spec.ttlStrategy.secondsAfterFailure}' 2>/dev/null)"
  if [ "$pod_gc" = "OnPodCompletion" ] && [ "$ttl_success" = "3600" ] && [ "$ttl_failure" = "86400" ]; then
    pass "workflow housekeeping: Pods GC after completion; success TTL=1h; failure TTL=24h"
  else
    fail "workflow housekeeping mismatch (podGC=${pod_gc:-<unset>}, successTTL=${ttl_success:-<unset>}, failureTTL=${ttl_failure:-<unset>})"
  fi
else
  fail "workflowtemplate red-agentic-triage missing"
fi
sem="$($K -n argo-events get cm triage-workflow-concurrency -o jsonpath='{.data.red-agentic-triage}' 2>/dev/null)"
if [ -n "$sem" ]; then
  pass "concurrency semaphore = $sem"
else
  fail "concurrency semaphore ConfigMap missing — WorkflowTemplate will not admit workflows"
fi
# Agent reachability, including the failure modes that return HTTP 200.
AG="$($K -n argo-events run agent-verify-$RANDOM --rm -i --restart=Never --quiet \
  --image=badouralix/curl-jq:alpine -- sh -c '
  cat > /tmp/r.json <<EOF
{"jsonrpc":"2.0","id":"verify","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Reply with one short sentence confirming you are reachable."}]}}}
EOF
  curl -s --max-time 120 -H "Content-Type: application/json" --data @/tmp/r.json \
    http://kagent-controller.kagent:8083/api/a2a/kagent/k8s-readonly-agent/ > /tmp/o.json || echo "{}" > /tmp/o.json
  printf "state=%s;err=%s;len=%s" \
    "$(jq -r ".result.status.state // \"none\"" /tmp/o.json)" \
    "$(jq -r "[.result.history[]?.metadata.kagent_error_code // empty]|unique|join(\",\")" /tmp/o.json)" \
    "$(jq -r "[.result.artifacts[]?.parts[]?|select(.kind==\"text\")|.text]|join(\"\")|length" /tmp/o.json)"
' 2>/dev/null)"
case "$AG" in
  *"state=completed"*"err=;"*)
    if [ "${AG##*len=}" -gt 0 ] 2>/dev/null; then
      pass "kagent read-only agent answering (${AG##*len=} chars)"
    else
      fail "kagent agent returned state=completed but NO text — tickets would carry a blank analysis"
    fi ;;
  *"err=;"*) fail "kagent agent reachable but task state not completed ($AG)" ;;
  "")         fail "kagent agent probe produced no output" ;;
  *)          fail "kagent agent returned an application error ($AG) — tickets will be labelled triage-agent-unavailable" ;;
esac

echo
echo "== 6. Standing state =="
info "open dedupe claims:  $($K -n argo-events get cm -o name 2>/dev/null | grep -c triage-dedupe)"
info "quarantined (DLQ):   $($K -n argo-events get cm -l triage-quarantine=true --no-headers 2>/dev/null | wc -l | tr -d ' ')"
info "triage workflows:    $($K -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage --no-headers 2>/dev/null | wc -l | tr -d ' ')"
failed="$($K -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage -o jsonpath='{range .items[*]}{.status.phase}{"\n"}{end}' 2>/dev/null | grep -cE 'Failed|Error')"
if [ "${failed:-0}" -gt 0 ]; then
  fail "$failed triage workflow(s) in Failed/Error — inspect with: kubectl -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage"
else
  pass "no failed triage workflows"
fi

echo
if [ "$rc" -eq 0 ]; then echo "RESULT: all checks passed"; else echo "RESULT: one or more checks FAILED"; fi
exit "$rc"
