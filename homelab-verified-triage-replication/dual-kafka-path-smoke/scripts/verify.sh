#!/usr/bin/env bash
set -euo pipefail
CTX="${2:-}"
[[ "${1:-}" == "--context" && -n "$CTX" ]] || { echo "usage: $0 --context <ctx>" >&2; exit 2; }
K="kubectl --context $CTX"
$K -n monitoring get deploy/dual-kafka-alloy
$K -n argo-events get deploy/dual-kafka-vector,eventsource/dual-kafka-topic-a,eventsource/dual-kafka-topic-b,sensor/dual-kafka-sensor-a,sensor/dual-kafka-sensor-b,workflowtemplate/dual-kafka-hello
$K -n argo-events logs -l eventsource-name=dual-kafka-topic-a --tail=200 | grep -q 'consumer group up and running' && echo 'PASS EventSource A connected' || echo 'CHECK EventSource A startup log'
$K -n argo-events logs -l eventsource-name=dual-kafka-topic-b --tail=200 | grep -q 'consumer group up and running' && echo 'PASS EventSource B connected' || echo 'CHECK EventSource B startup log'
