#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$BUNDLE_DIR/../.." && pwd)"
MANAGEMENT_CONTEXT=""
WORKER_CONTEXT=""
MODEL_CONFIG="default-model-config"
KEEP=false
RUN_ID="$(date +%s)-$$-$RANDOM"
TARGET_NAMESPACE="fleet-mcp-smoke-${RUN_ID}"
MCP_NAMESPACE="aks-mcp-smoke-${RUN_ID}"
TARGET_SERVICE_ACCOUNT="fleet-mcp-smoke-${RUN_ID}"
TARGET_BINDING="fleet-mcp-view-${RUN_ID}"
PROOF_CONFIGMAP="fleet-mcp-proof"
MANAGEMENT_RELEASE="fleet-mgmt-${RUN_ID}"
WORKER_RELEASE="fleet-worker-${RUN_ID}"
MANAGEMENT_MCP_NAME="aks-mcp-management-smoke"
WORKER_MCP_NAME="aks-mcp-worker-smoke"
MANAGEMENT_AGENT_NAME="aks-management-smoke-agent-${RUN_ID}"
WORKER_AGENT_NAME="aks-worker-smoke-agent-${RUN_ID}"
MANAGEMENT_REMOTE_NAME="aks-mcp-management-smoke-${RUN_ID}"
WORKER_REMOTE_NAME="aks-mcp-worker-smoke-${RUN_ID}"
TEST_DIR="$(mktemp -d)"
MANAGEMENT_MARKER=""
WORKER_MARKER=""

usage() {
  echo "usage: $0 --management-context CONTEXT --worker-context CONTEXT [--model-config NAME] [--keep]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --management-context) MANAGEMENT_CONTEXT="$2"; shift 2 ;;
    --worker-context) WORKER_CONTEXT="$2"; shift 2 ;;
    --model-config) MODEL_CONFIG="$2"; shift 2 ;;
    --keep) KEEP=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$MANAGEMENT_CONTEXT" && -n "$WORKER_CONTEXT" ]] || { usage >&2; exit 2; }
for command_name in kubectl helm jq base64 od; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "missing command: $command_name" >&2; exit 2; }
done
MANAGEMENT_MARKER="mcp-$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
WORKER_MARKER="mcp-$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"

cleanup() {
  rm -rf "$TEST_DIR"
  if [[ "$KEEP" == "true" ]]; then
    echo "KEEP=true: live smoke resources retained"
    return
  fi
  kubectl --context "$MANAGEMENT_CONTEXT" -n kagent delete agent \
    "$MANAGEMENT_AGENT_NAME" "$WORKER_AGENT_NAME" --ignore-not-found >/dev/null 2>&1 || true
  kubectl --context "$MANAGEMENT_CONTEXT" -n kagent delete remotemcpserver \
    "$MANAGEMENT_REMOTE_NAME" "$WORKER_REMOTE_NAME" --ignore-not-found >/dev/null 2>&1 || true
  helm --kube-context "$MANAGEMENT_CONTEXT" uninstall "$MANAGEMENT_RELEASE" -n "$MCP_NAMESPACE" >/dev/null 2>&1 || true
  helm --kube-context "$MANAGEMENT_CONTEXT" uninstall "$WORKER_RELEASE" -n "$MCP_NAMESPACE" >/dev/null 2>&1 || true
  kubectl --context "$MANAGEMENT_CONTEXT" delete namespace "$MCP_NAMESPACE" --ignore-not-found >/dev/null 2>&1 || true
  for context_name in "$MANAGEMENT_CONTEXT" "$WORKER_CONTEXT"; do
    kubectl --context "$context_name" delete clusterrolebinding "$TARGET_BINDING" --ignore-not-found >/dev/null 2>&1 || true
    kubectl --context "$context_name" delete namespace "$TARGET_NAMESPACE" --ignore-not-found >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

create_readonly_kubeconfig() {
  local context_name="$1" alias_name="$2" output_path="$3" marker="$4"
  local server ca_data token

  kubectl --context "$context_name" create namespace "$TARGET_NAMESPACE" >/dev/null
  kubectl --context "$context_name" -n "$TARGET_NAMESPACE" \
    create serviceaccount "$TARGET_SERVICE_ACCOUNT" >/dev/null
  kubectl --context "$context_name" create clusterrolebinding "$TARGET_BINDING" \
    --clusterrole=view --serviceaccount="$TARGET_NAMESPACE:$TARGET_SERVICE_ACCOUNT" >/dev/null
  kubectl --context "$context_name" -n "$TARGET_NAMESPACE" create configmap "$PROOF_CONFIGMAP" \
    --from-literal=marker="$marker" >/dev/null

  server="$(kubectl --context "$context_name" config view --minify --raw -o jsonpath='{.clusters[0].cluster.server}')"
  ca_data="$(kubectl --context "$context_name" config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')"
  token="$(kubectl --context "$context_name" -n "$TARGET_NAMESPACE" create token "$TARGET_SERVICE_ACCOUNT" --duration=1h)"
  [[ -n "$server" && -n "$token" ]] || { echo "could not generate source kubeconfig" >&2; exit 1; }

  if [[ -n "$ca_data" ]]; then
    printf '%s' "$ca_data" | base64 --decode >"$TEST_DIR/${alias_name}.ca"
    kubectl --kubeconfig "$output_path" config set-cluster "$alias_name" \
      --server="$server" --certificate-authority="$TEST_DIR/${alias_name}.ca" \
      --embed-certs=true >/dev/null
  else
    kubectl --kubeconfig "$output_path" config set-cluster "$alias_name" \
      --server="$server" --insecure-skip-tls-verify=true >/dev/null
  fi
  kubectl --kubeconfig "$output_path" config set-credentials "$alias_name" --token="$token" >/dev/null
  kubectl --kubeconfig "$output_path" config set-context "$alias_name" \
    --cluster="$alias_name" --user="$alias_name" >/dev/null
  kubectl --kubeconfig "$output_path" config use-context "$alias_name" >/dev/null
  chmod 600 "$output_path"
}

echo "Creating one-hour read-only test identities in two explicitly selected clusters"
create_readonly_kubeconfig "$MANAGEMENT_CONTEXT" management-smoke "$TEST_DIR/management.config" "$MANAGEMENT_MARKER"
create_readonly_kubeconfig "$WORKER_CONTEXT" worker-smoke "$TEST_DIR/worker.config" "$WORKER_MARKER"

kubectl --kubeconfig "$TEST_DIR/management.config" get namespace "$TARGET_NAMESPACE" -o name >/dev/null
kubectl --kubeconfig "$TEST_DIR/worker.config" get namespace "$TARGET_NAMESPACE" -o name >/dev/null
echo "PASS source credentials and direct connectivity"

kubectl --context "$MANAGEMENT_CONTEXT" create namespace "$MCP_NAMESPACE" >/dev/null
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MCP_NAMESPACE" create secret generic fleet-static-sources \
  --from-file=management.config="$TEST_DIR/management.config" \
  --from-file=worker.config="$TEST_DIR/worker.config" \
  --dry-run=client -o yaml | kubectl --context "$MANAGEMENT_CONTEXT" apply -f - >/dev/null
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MCP_NAMESPACE" create secret generic aks-mcp-fleet-kubeconfig \
  --from-literal=bootstrap='' --dry-run=client -o yaml \
  | kubectl --context "$MANAGEMENT_CONTEXT" apply -f - >/dev/null

jq -n --arg namespace "$TARGET_NAMESPACE" '{clusters:[
  {alias:"management-smoke",provider:"static",sourceFile:"management.config",smokeNamespace:$namespace},
  {alias:"worker-smoke",provider:"static",sourceFile:"worker.config",smokeNamespace:$namespace}
]}' >"$TEST_DIR/registry.json"

REGISTRY_PATH="$TEST_DIR/registry.json" \
STATIC_SOURCE_DIR="$TEST_DIR" \
WORK_DIR="$TEST_DIR/refresh" \
CONTROL_CONTEXT="$MANAGEMENT_CONTEXT" \
TARGET_NAMESPACE="$MCP_NAMESPACE" \
ALLOW_STATIC_SOURCES=true \
ALLOW_STATIC_CREDENTIALS=true \
ROLLOUT_ON_CHANGE=false \
"$BUNDLE_DIR/scripts/refresh-fleet-kubeconfig.sh" | grep -q '^PUBLISHED contexts=2 '
echo "PASS candidate merge, validation, and atomic Secret replacement"

install_mcp_shard() {
  local release_name="$1" mcp_name="$2" secret_key="$3"
  helm upgrade --install "$release_name" "$REPO_ROOT/platform/aks-mcp/chart" \
    --kube-context "$MANAGEMENT_CONTEXT" --namespace "$MCP_NAMESPACE" \
    --set fullnameOverride="$mcp_name" \
    --set image.tag=v0.0.19 \
    --set image.pullPolicy=IfNotPresent \
    --set app.transport=streamable-http \
    --set app.accessLevel=readonly \
    --set app.cache=false \
    --set "app.allowedHosts[0]=$mcp_name.$MCP_NAMESPACE.svc.cluster.local" \
    --set-json 'config.enabledComponents=["kubectl"]' \
    --set kubeconfig.enabled=true \
    --set kubeconfig.secretName=aks-mcp-fleet-kubeconfig \
    --set kubeconfig.key="$secret_key" \
    --set kubeconfig.optional=false \
    --set kubeconfig.expectedCurrentContext="${secret_key%.config}" \
    --set rbac.create=false \
    --set serviceAccount.automount=false \
    --set resources.requests.cpu=1m \
    --set resources.requests.memory=64Mi \
    --set resources.limits.cpu=250m \
    --set resources.limits.memory=256Mi \
    --set-json 'extraEnv=[{"name":"KUBECONFIG","value":"/home/mcp/.kube/config"}]' \
    --wait --timeout 5m >/dev/null
}

install_mcp_shard "$MANAGEMENT_RELEASE" "$MANAGEMENT_MCP_NAME" management-smoke.config
install_mcp_shard "$WORKER_RELEASE" "$WORKER_MCP_NAME" worker-smoke.config
echo "PASS two AKS-MCP shards started from separate keys in one read-only Secret"

kubectl --context "$MANAGEMENT_CONTEXT" -n kagent apply -f - >/dev/null <<EOF
apiVersion: kagent.dev/v1alpha2
kind: RemoteMCPServer
metadata:
  name: $MANAGEMENT_REMOTE_NAME
spec:
  description: Ephemeral management-target AKS-MCP homelab smoke.
  protocol: STREAMABLE_HTTP
  url: http://$MANAGEMENT_MCP_NAME.$MCP_NAMESPACE.svc.cluster.local:8000/mcp
---
apiVersion: kagent.dev/v1alpha2
kind: RemoteMCPServer
metadata:
  name: $WORKER_REMOTE_NAME
spec:
  description: Ephemeral worker-target AKS-MCP homelab smoke.
  protocol: STREAMABLE_HTTP
  url: http://$WORKER_MCP_NAME.$MCP_NAMESPACE.svc.cluster.local:8000/mcp
---
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: $MANAGEMENT_AGENT_NAME
spec:
  type: Declarative
  description: Ephemeral read-only management-target smoke agent.
  declarative:
    runtime: go
    modelConfig: $MODEL_CONFIG
    deployment:
      replicas: 1
      resources:
        requests:
          cpu: 1m
          memory: 64Mi
        limits:
          cpu: 250m
          memory: 256Mi
    systemMessage: |
      You are the read-only verifier for fixed alias management-smoke. Reject
      every other alias. Use call_kubectl exactly once with command:
      kubectl get configmap $PROOF_CONFIGMAP --namespace $TARGET_NAMESPACE -o jsonpath='{.data.marker}'
      Never pass context, kubeconfig, server, token, or certificate flags.
      Never mutate anything and never
      print credentials, kubeconfig contents, certificates, tokens, or endpoints.
      Return TARGET_OK management-smoke followed by the exact marker returned by
      the tool. Do not invent or transform the marker.
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: $MANAGEMENT_REMOTE_NAME
          namespace: kagent
          toolNames: [call_kubectl]
---
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: $WORKER_AGENT_NAME
spec:
  type: Declarative
  description: Ephemeral read-only worker-target smoke agent.
  declarative:
    runtime: go
    modelConfig: $MODEL_CONFIG
    deployment:
      replicas: 1
      resources:
        requests:
          cpu: 1m
          memory: 64Mi
        limits:
          cpu: 250m
          memory: 256Mi
    systemMessage: |
      You are the read-only verifier for fixed alias worker-smoke. Reject every
      other alias. Use call_kubectl exactly once with command:
      kubectl get configmap $PROOF_CONFIGMAP --namespace $TARGET_NAMESPACE -o jsonpath='{.data.marker}'
      Never pass context, kubeconfig, server, token, or certificate flags.
      Never mutate anything and never print credentials, kubeconfig contents,
      certificates, tokens, or endpoints. Return TARGET_OK worker-smoke followed
      by the exact marker returned by the tool. Do not invent or transform it.
    tools:
      - type: McpServer
        mcpServer:
          apiGroup: kagent.dev
          kind: RemoteMCPServer
          name: $WORKER_REMOTE_NAME
          namespace: kagent
          toolNames: [call_kubectl]
EOF

wait_for_pair() {
  local remote_name="$1" agent_name="$2" remote_json="" ready=""
  for _ in $(seq 1 60); do
    remote_json="$(kubectl --context "$MANAGEMENT_CONTEXT" -n kagent get remotemcpserver "$remote_name" -o json 2>/dev/null || true)"
    ready="$(kubectl --context "$MANAGEMENT_CONTEXT" -n kagent get agent "$agent_name" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
    if [[ "$ready" == "True" ]] && jq -e '
      (.status.conditions[]? | select(.type == "Accepted" and .status == "True"))
      and ([.status.discoveredTools[]?.name] | sort == ["call_kubectl"])
    ' <<<"$remote_json" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "MCP/Agent pair was not ready: $remote_name / $agent_name" >&2
  return 1
}

wait_for_pair "$MANAGEMENT_REMOTE_NAME" "$MANAGEMENT_AGENT_NAME"
wait_for_pair "$WORKER_REMOTE_NAME" "$WORKER_AGENT_NAME"
echo "PASS two RemoteMCPServers Accepted and two fixed-target Agents Ready"

for pair in "management-smoke:$MANAGEMENT_AGENT_NAME:$MANAGEMENT_MARKER" "worker-smoke:$WORKER_AGENT_NAME:$WORKER_MARKER"; do
  IFS=: read -r alias_name agent_name expected_marker <<<"$pair"
  response=""
  receipt_file="$TEST_DIR/$alias_name-receipt.json"
  invoke_rc=1
  for attempt in 1 2; do
    set +e
    response="$($REPO_ROOT/scripts/kagent-a2a-invoke.sh \
      --context "$MANAGEMENT_CONTEXT" --local-port "$((18080 + RANDOM % 1000))" \
      --agent "$agent_name" --timeout 120 \
      --receipt-file "$receipt_file" \
      --text "{\"clusterAlias\":\"$alias_name\",\"question\":\"Read and return the isolated proof marker.\"}")"
    invoke_rc=$?
    set -e
    [[ "$invoke_rc" == "0" ]] && grep -q 'TARGET_OK' <<<"$response" && break
    [[ "$attempt" == "1" ]] && echo "A2A attempt 1 did not produce TARGET_OK for $alias_name; retrying once" >&2
  done
  [[ "$invoke_rc" == "0" ]] || { echo "A2A transport failed twice for $alias_name" >&2; exit 1; }
  grep -q 'TARGET_OK' <<<"$response" || {
    echo "agent did not return TARGET_OK for $alias_name; sanitized response follows:" >&2
    printf '%s\n' "$response" >&2
    exit 1
  }
  grep -q "$alias_name" <<<"$response" || { echo "agent did not identify $alias_name" >&2; exit 1; }
  grep -Fq "$expected_marker" <<<"$response" \
    || { echo "agent did not return the target marker for $alias_name" >&2; exit 1; }
  jq -e --arg marker "$expected_marker" '
    [.result.history[]?.parts[]?
      | select(.metadata.kagent_type == "function_response"
        and .data.name == "call_kubectl")] as $calls
    | ($calls | length) == 1
      and ($calls[0].data.response.isError == false)
      and any($calls[0]..; type == "string" and contains($marker))
  ' "$receipt_file" >/dev/null \
    || { echo "A2A receipt lacks one successful marker-bearing call_kubectl trace for $alias_name" >&2; exit 1; }
  echo "PASS Argo-style alias routing reached $alias_name through its AKS-MCP shard"
done

echo "HOMELAB_SMOKE_OK contexts=2 secrets=1 mcp_shards=2 agents=2 a2a=2"
