#!/usr/bin/env bash
set -euo pipefail

: "${HOST_CONTEXT:?set HOST_CONTEXT to the management-cluster kubeconfig context}"
: "${SOURCE_CONTEXTS:?set SOURCE_CONTEXTS to space-separated source-context=stable-alias mappings}"

for command_name in kubectl helm jq openssl curl npx; do
  command -v "$command_name" >/dev/null || {
    echo "missing required command: $command_name" >&2
    exit 1
  }
done

for mapping in $SOURCE_CONTEXTS; do
  source_context=${mapping%%=*}
  alias_name=${mapping#*=}
  test "$source_context" != "$alias_name" || {
    echo "invalid SOURCE_CONTEXTS entry: $mapping" >&2
    exit 1
  }
  kubectl config get-contexts -o name | grep -Fx "$source_context" >/dev/null
  kubectl --context "$source_context" get --raw=/readyz >/dev/null
  node_count=$(kubectl --context "$source_context" get nodes -o name | wc -l | tr -d ' ')
  version=$(kubectl --context "$source_context" version -o json | jq -r '.serverVersion.gitVersion')
  echo "PREFLIGHT_CONTEXT_OK source=$source_context alias=$alias_name nodes=$node_count version=$version"
done

kubectl --context "$HOST_CONTEXT" get crd \
  remotemcpservers.kagent.dev \
  agentgatewaybackends.agentgateway.dev \
  agentgatewaypolicies.agentgateway.dev \
  httproutes.gateway.networking.k8s.io >/dev/null

gateway_programmed=$(kubectl --context "$HOST_CONTEXT" -n agentgateway-system \
  get gateway ai-gateway -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}')
test "$gateway_programmed" = "True"

if kubectl --context "$HOST_CONTEXT" -n default get deployment kubectl-mcp >/dev/null 2>&1; then
  uid=$(kubectl --context "$HOST_CONTEXT" -n default get deployment kubectl-mcp -o jsonpath='{.metadata.uid}')
  generation=$(kubectl --context "$HOST_CONTEXT" -n default get deployment kubectl-mcp -o jsonpath='{.metadata.generation}')
  echo "UNRELATED_BASELINE deployment=default/kubectl-mcp uid=$uid generation=$generation"
else
  echo "UNRELATED_BASELINE deployment=default/kubectl-mcp absent"
fi

echo "PREFLIGHT_OK host=$HOST_CONTEXT gateway=agentgateway-system/ai-gateway"
