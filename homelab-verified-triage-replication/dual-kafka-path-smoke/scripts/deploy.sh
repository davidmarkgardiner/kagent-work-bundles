#!/usr/bin/env bash
set -euo pipefail
CTX="${2:-}"
[[ "${1:-}" == "--context" && -n "$CTX" ]] || { echo "usage: $0 --context <ctx>" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K="kubectl --context $CTX"
for check in \
  "$K -n monitoring get serviceaccount alloy" \
  "$K -n argo-events get serviceaccount argo-events-sa" \
  "$K -n argo-events get eventbus default" \
  "$K -n argo-events get secret confluent-credentials"; do
  eval "$check" >/dev/null || { echo "MISSING prerequisite: $check" >&2; exit 1; }
done
$K apply --dry-run=server -k "$ROOT/config"
$K apply -k "$ROOT/config"
$K -n monitoring rollout status deploy/dual-kafka-alloy --timeout=120s
$K -n argo-events rollout status deploy/dual-kafka-vector --timeout=120s
echo "DEPLOY_OK: run bash scripts/verify.sh --context $CTX"
