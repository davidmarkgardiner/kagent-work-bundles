#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --values /path/to/private/values.env --workflow WORKFLOW_NAME" >&2
  exit 2
}

[[ "${1:-}" == "--values" && -n "${2:-}" && "${3:-}" == "--workflow" && -n "${4:-}" ]] || usage
VALUES="$2"
WORKFLOW_NAME="$4"
[[ -f "$VALUES" ]] || { echo "Values file not found: $VALUES" >&2; exit 2; }

# Operator-selected values file is validated above.
set -a
# shellcheck disable=SC1090
source "$VALUES"
set +a
: "${MANAGEMENT_CONTEXT:?MANAGEMENT_CONTEXT is required}"
: "${MANAGEMENT_NAMESPACE:?MANAGEMENT_NAMESPACE is required}"
: "${KAGENT_NAMESPACE:?KAGENT_NAMESPACE is required}"
: "${KAGENT_AGENT_NAME:?KAGENT_AGENT_NAME is required}"
: "${KAGENT_CONTROLLER_DEPLOYMENT:?KAGENT_CONTROLLER_DEPLOYMENT is required}"
: "${AKS_MCP_NAMESPACE:?AKS_MCP_NAMESPACE is required}"
: "${AKS_MCP_LABEL:?AKS_MCP_LABEL is required}"

km() { kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" "$@"; }
check_selected_image() {
  local namespace="$1" selector="$2" expected="$3" actual
  [[ -z "$expected" ]] && return 0
  actual="$(kubectl --context "$MANAGEMENT_CONTEXT" -n "$namespace" get pods -l "$selector" -o jsonpath='{range .items[*].spec.containers[*]}{.image}{"\n"}{end}')"
  printf '%s\n' "$actual"
  grep -Fqx "$expected" <<<"$actual" || { echo "Expected selected-pod image not found: ${expected}" >&2; exit 1; }
  echo "IMAGE_OK selector=${selector} image=${expected}"
}

echo "== Workflow pods and logs =="
km get workflow "$WORKFLOW_NAME" -o yaml
km get pods -l "workflows.argoproj.io/workflow=$WORKFLOW_NAME" -o wide
if command -v argo >/dev/null 2>&1; then
  argo --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" logs "$WORKFLOW_NAME" --all-containers
else
  echo "Argo CLI not found; inspect each listed workflow pod with kubectl logs."
fi

echo "== Declared read-only agent configuration =="
kubectl --context "$MANAGEMENT_CONTEXT" -n "$KAGENT_NAMESPACE" get agents "$KAGENT_AGENT_NAME" -o yaml
kubectl --context "$MANAGEMENT_CONTEXT" -n "$KAGENT_NAMESPACE" get deployment "$KAGENT_CONTROLLER_DEPLOYMENT" -o wide

echo "== AKS MCP runtime and correlated recent logs =="
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" get pods -l "$AKS_MCP_LABEL" -o wide
check_selected_image "$AKS_MCP_NAMESPACE" "$AKS_MCP_LABEL" "${AKS_MCP_EXPECTED_IMAGE:-}"
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" logs -l "$AKS_MCP_LABEL" --since=30m

echo "TRIAGE_TOOL_CHECK_COMPLETE: manually confirm the agent response, AKS MCP read request and GitLab ticket all refer to the same controlled incident."
