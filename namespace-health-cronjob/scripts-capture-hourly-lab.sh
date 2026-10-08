#!/usr/bin/env bash
# Read-only completion of the 13:00-17:00 UTC kind trial evidence.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts-capture-hourly-lab.sh EMPTY_OUTPUT_DIR" >&2
  exit 2
fi

bundle_dir="$(cd "$(dirname "$0")" && pwd)"
out_dir="$1"
if [[ -e "$out_dir" ]] && [[ -n "$(ls -A "$out_dir")" ]]; then
  echo "output directory must be empty" >&2
  exit 2
fi
mkdir -p "$out_dir"

for hour in 13 14 15 16 17; do
  slot="2026-10-07T${hour}:00:00Z"
  docker run --rm --network kind \
    -v "$bundle_dir/scripts-capture-topic.py:/app/capture-topic.py:ro" \
    -e KAFKA_BOOTSTRAP_SERVERS=namespace-health-control-plane:30092 \
    -e KAFKA_SECURITY_PROTOCOL=PLAINTEXT \
    -e LAB_PLAINTEXT=true \
    -e TRUSTED_CLUSTER=kind-namespace-health \
    namespace-health:lab-arm64 python /app/capture-topic.py \
    namespace-health-trial-v1 "$slot" --historical \
    > "$out_dir/${hour}00.json" 2> "$out_dir/${hour}00.meta.json"
done

kubectl --context kind-namespace-health -n health-trial get workflows \
  -l app.kubernetes.io/name=namespace-health-receipt -o json \
  > "$out_dir/workflows.json"
kubectl --context kind-namespace-health -n health-trial get cronjob namespace-health-assessor -o json \
  > "$out_dir/cronjob.json"
cp /tmp/namespace-health-scheduled-monitor-state/monitor.json "$out_dir/external-monitor.json"
cp /tmp/namespace-health-alerts.jsonl "$out_dir/alert-webhook.jsonl"
echo "captured historical broker values and current receiver state in $out_dir"
