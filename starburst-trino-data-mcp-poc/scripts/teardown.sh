#!/usr/bin/env sh
set -eu
context=red
[ "$#" -gt 0 ] && context="$1"
root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
kubectl --context "$context" delete -f "$root/kagent-agent.yaml" --ignore-not-found
helm uninstall trino --namespace data-mcp-poc --kube-context "$context" 2>/dev/null || true
kubectl --context "$context" delete namespace data-mcp-poc --ignore-not-found
