#!/usr/bin/env bash
set -euo pipefail
CTX="${2:-}"
[[ "${1:-}" == "--context" && -n "$CTX" ]] || { echo "usage: $0 --context <ctx>" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
kubectl --context "$CTX" delete -k "$ROOT/config" --ignore-not-found
kubectl --context "$CTX" -n argo-events delete workflow -l app.kubernetes.io/part-of=dual-kafka-path-smoke --ignore-not-found
