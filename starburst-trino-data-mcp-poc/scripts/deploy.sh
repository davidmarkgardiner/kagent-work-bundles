#!/usr/bin/env sh
set -eu
context=red
[ "$#" -gt 0 ] && context="$1"
root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
kubectl --context "$context" create namespace data-mcp-poc --dry-run=client -o yaml | kubectl --context "$context" apply -f -
helm upgrade --install trino trino/trino --version 1.41.0 --namespace data-mcp-poc --kube-context "$context" --values "$root/values-trino.yaml" --wait --timeout 5m
kubectl --context "$context" apply -f "$root/mcp-adapter.yaml"
kubectl --context "$context" -n data-mcp-poc rollout status deployment/trino-readonly-mcp --timeout=5m
# The synthetic in-memory table disappears if Trino restarts. Recreate this
# scoped disposable Job on every deploy so the dataset and its receipt are fresh.
kubectl --context "$context" -n data-mcp-poc delete job/trino-data-mcp-seed --ignore-not-found
kubectl --context "$context" apply -f "$root/seed-job.yaml"
kubectl --context "$context" -n data-mcp-poc wait --for=condition=complete job/trino-data-mcp-seed --timeout=2m
kubectl --context "$context" apply -f "$root/kagent-agent.yaml"
