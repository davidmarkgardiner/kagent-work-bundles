#!/usr/bin/env bash
set -euo pipefail
CTX="${2:-}"
[[ "${1:-}" == "--context" && -n "$CTX" ]] || { echo "usage: $0 --context <ctx>" >&2; exit 2; }
K="kubectl --context $CTX"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
NAME="dual-kafka-smoke-${STAMP,,}"
before_a="$($K -n argo-events get wf -l 'dual-kafka-path=a' --no-headers 2>/dev/null | wc -l | tr -d ' ')"
before_b="$($K -n argo-events get wf -l 'dual-kafka-path=b' --no-headers 2>/dev/null | wc -l | tr -d ' ')"
$K -n dual-kafka-smoke run "$NAME" --image=busybox:1.36 --restart=Never -- sh -c "echo DUAL-KAFKA-SMOKE ${STAMP} ERROR; sleep 45"
deadline=$(( $(date +%s) + 180 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  now_a="$($K -n argo-events get wf -l 'dual-kafka-path=a' --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  now_b="$($K -n argo-events get wf -l 'dual-kafka-path=b' --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  [ "$now_a" -gt "$before_a" ] && [ "$now_b" -gt "$before_b" ] && break
  sleep 5
done
echo "== Path A =="; $K -n argo-events get wf -l 'dual-kafka-path=a' --sort-by=.metadata.creationTimestamp
echo "== Path B =="; $K -n argo-events get wf -l 'dual-kafka-path=b' --sort-by=.metadata.creationTimestamp
echo "== Vector Kafka counters =="
$K -n argo-events run dual-kafka-metrics-$RANDOM --rm -i --restart=Never --quiet --image=badouralix/curl-jq:alpine -- sh -c 'curl -s http://dual-kafka-vector.argo-events:9090/metrics' | grep 'component_id="kafka_[ab]"' || true
$K -n dual-kafka-smoke delete pod "$NAME" --ignore-not-found
