#!/usr/bin/env bash
set -euo pipefail
CTX="${2:-}"
[[ "${1:-}" == "--context" && -n "$CTX" ]] || { echo "usage: $0 --context <ctx>" >&2; exit 2; }
K="kubectl --context $CTX"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="dual-kafka-marker"
before_a="$($K -n argo-events get wf -l 'dual-kafka-path=a' --no-headers 2>/dev/null | wc -l | tr -d ' ')"
before_b="$($K -n argo-events get wf -l 'dual-kafka-path=b' --no-headers 2>/dev/null | wc -l | tr -d ' ')"
cleanup() {
  $K -n dual-kafka-smoke delete pod "$NAME" --ignore-not-found >/dev/null 2>&1 || true
}
trap cleanup EXIT
$K -n dual-kafka-smoke delete pod "$NAME" --ignore-not-found --wait=true
$K apply -k "$HERE/fixtures"
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
$K -n argo-events run dual-kafka-metrics-$RANDOM --rm -i --restart=Never --quiet --image=badouralix/curl-jq:alpine -- sh -c 'curl -s http://dual-kafka-vector.argo-events:9090/metrics' | grep 'vector_kafka_produced_messages_total.*component_id="kafka_[ab]"' || true
if [ "$now_a" -le "$before_a" ] || [ "$now_b" -le "$before_b" ]; then
  echo "FAILED: marker did not produce a new hello Workflow on both paths within 180 seconds." >&2
  exit 1
fi
echo "DUAL_KAFKA_PATH_SMOKE: passed (both paths produced a hello Workflow)"
