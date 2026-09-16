#!/usr/bin/env bash
set -euo pipefail

WORKER_CONTEXT="${1:?usage: verify-live.sh WORKER_CONTEXT MANAGER_CONTEXT RENDER_DIR AKS_MCP_SERVER_NAME}"
MANAGER_CONTEXT="${2:?usage: verify-live.sh WORKER_CONTEXT MANAGER_CONTEXT RENDER_DIR AKS_MCP_SERVER_NAME}"
RENDER_DIR="${3:?usage: verify-live.sh WORKER_CONTEXT MANAGER_CONTEXT RENDER_DIR AKS_MCP_SERVER_NAME}"
AKS_MCP_SERVER_NAME="${4:?usage: verify-live.sh WORKER_CONTEXT MANAGER_CONTEXT RENDER_DIR AKS_MCP_SERVER_NAME}"

kubectl --context "$WORKER_CONTEXT" apply --dry-run=server -f "$RENDER_DIR/worker.yaml" >/dev/null
kubectl --context "$MANAGER_CONTEXT" apply --dry-run=server -f "$RENDER_DIR/manager.yaml" >/dev/null

kubectl --context "$MANAGER_CONTEXT" -n kagent get remotemcpserver "$AKS_MCP_SERVER_NAME" -o yaml >/dev/null
echo "Server dry-runs and manager dependency check passed"
