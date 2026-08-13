#!/usr/bin/env sh
set -eu
context=red
[ "$#" -gt 0 ] && context="$1"
kubectl --context "$context" delete namespace postgres-dab-mcp-poc --ignore-not-found
kubectl --context "$context" -n kagent delete agent/postgres-dab-compliance-lab-agent --ignore-not-found
kubectl --context "$context" -n kagent delete remotemcpserver/postgres-dab-compliance-mcp --ignore-not-found
kubectl --context "$context" -n kagent delete agent/postgres-kubernetes-inventory-lab-agent --ignore-not-found
kubectl --context "$context" -n kagent delete remotemcpserver/postgres-kubernetes-inventory-readonly-mcp --ignore-not-found
