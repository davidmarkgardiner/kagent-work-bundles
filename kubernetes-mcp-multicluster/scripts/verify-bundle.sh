#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO_ROOT=$(cd "$BUNDLE_DIR/../.." && pwd)
LIVE_VALIDATE=${LIVE_VALIDATE:-auto}

# shellcheck source=load-config.sh
source "$BUNDLE_DIR/scripts/load-config.sh"
load_bundle_config "$BUNDLE_DIR"
test -f "$CHART_REF/Chart.yaml" || {
  echo "local Helm chart not found: $CHART_REF/Chart.yaml" >&2
  exit 1
}
actual_chart_version=$(helm show chart "$CHART_REF" | awk '$1 == "version:" {print $2; exit}')
test "$actual_chart_version" = "$CHART_VERSION" || {
  echo "chart version mismatch: expected=$CHART_VERSION actual=$actual_chart_version" >&2
  exit 1
}

for script in "$BUNDLE_DIR"/scripts/*.sh; do
  bash -n "$script"
done

if command -v shellcheck >/dev/null; then
  shellcheck -x -P "$BUNDLE_DIR/scripts" "$BUNDLE_DIR"/scripts/*.sh
fi

# shellcheck source=mcp-json.sh
source "$BUNDLE_DIR/scripts/mcp-json.sh"
multi_content_fixture='{"jsonrpc":"2.0","id":1,"result":{"content":[{"text":"other-cluster-marker"},{"text":"expected-cluster-marker"}]}}'
printf '%s' "$multi_content_fixture" | mcp_response_contains_marker expected-cluster-marker >/dev/null
printf '%s' "$multi_content_fixture" | mcp_response_contains_marker other-cluster-marker >/dev/null
if printf '%s' "$multi_content_fixture" | mcp_response_contains_marker absent-marker >/dev/null; then
  echo "multi-content marker self-test returned a false positive" >&2
  exit 1
fi
test "$(mcp_extract_jsonrpc_response "$multi_content_fixture")" = "$multi_content_fixture"
test "$(mcp_extract_jsonrpc_response "data: $multi_content_fixture")" = "$multi_content_fixture"

# shellcheck source=token-utils.sh
source "$BUNDLE_DIR/scripts/token-utils.sh"
jwt_payload=$(printf '%s' '{"exp":4102444800}' | openssl base64 -A | tr '/+' '_-' | tr -d '=')
test "$(jwt_expiry_epoch "header.$jwt_payload.signature")" = "4102444800"
unset jwt_payload

# shellcheck source=secret-utils.sh
source "$BUNDLE_DIR/scripts/secret-utils.sh"
secret_fixture='{"items":[{"metadata":{"name":"active"}},{"metadata":{"name":"previous"}},{"metadata":{"name":"older"}}]}'
test "$(printf '%s' "$secret_fixture" | credential_secrets_to_prune active previous)" = "older"

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kubernetes-mcp-chart.XXXXXX")
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

python3 - "$BUNDLE_DIR" <<'PY'
import pathlib
import sys
import yaml

bundle_dir = pathlib.Path(sys.argv[1])

for path in bundle_dir.rglob("*.yaml"):
    with path.open(encoding="utf-8") as stream:
        list(yaml.safe_load_all(stream))
PY

kubectl kustomize "$BUNDLE_DIR" >"$tmp_dir/kustomize-rendered.yaml"

# shellcheck disable=SC2206
tools=( $TOOL_ALLOWLIST_LIST )
tool_set_args=()
for tool_index in "${!tools[@]}"; do
  tool_set_args+=(--set-string "config.enabled_tools[$tool_index]=${tools[$tool_index]}")
done

chart_dir=$CHART_REF
helm lint "$chart_dir" -f "$BUNDLE_DIR/values.yaml" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${tool_set_args[@]}" >/dev/null
helm template kubernetes-mcp-fleet "$chart_dir" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${tool_set_args[@]}" >"$tmp_dir/helm-rendered.yaml"

expected_image="$IMAGE_REGISTRY/$IMAGE_REPOSITORY:$IMAGE_VERSION"
python3 - "$tmp_dir/helm-rendered.yaml" "$tmp_dir/kustomize-rendered.yaml" \
  "$expected_image" "$TOOL_ALLOWLIST" "$TARGET_API_CIDRS" \
  "$AGENTGATEWAY_MCP_URL" "$AGENTGATEWAY_NAMESPACE" <<'PY'
import ipaddress
import json
import re
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as stream:
    helm_documents = list(yaml.safe_load_all(stream))
with open(sys.argv[2], encoding="utf-8") as stream:
    kustomize_documents = list(yaml.safe_load_all(stream))
expected_image = sys.argv[3]
expected_tools = sys.argv[4].split(",")
expected_cidrs = sys.argv[5].split(",")
expected_gateway_url = sys.argv[6]
expected_gateway_namespace = sys.argv[7]

images = [
    container["image"]
    for document in helm_documents
    if document and document.get("kind") == "Deployment"
    for container in document["spec"]["template"]["spec"]["containers"]
]
if images != [expected_image]:
    raise SystemExit(f"rendered image mismatch: expected={expected_image} actual={images}")

deployment = next(document for document in helm_documents if document and document.get("kind") == "Deployment")
config_map = next(document for document in helm_documents if document and document.get("kind") == "ConfigMap")
tool_line = re.search(r'^enabled_tools = (\[.*\])$', config_map["data"]["config.toml"], re.MULTILINE)
helm_tools = json.loads(tool_line.group(1)) if tool_line else None
if helm_tools != expected_tools:
    raise SystemExit(f"Helm tool allowlist mismatch: {helm_tools}")
annotation = deployment["spec"]["template"]["metadata"]["annotations"].get(
    "kubernetes-mcp-fleet/credential-revision"
)
if annotation != "kubernetes-mcp-fleet-kubeconfig-example":
    raise SystemExit(f"credential revision annotation did not render: {annotation}")

agent = next(document for document in kustomize_documents if document and document.get("kind") == "Agent")
agent_tools = agent["spec"]["declarative"]["tools"][0]["mcpServer"]["toolNames"]
if agent_tools != expected_tools:
    raise SystemExit(f"Agent tool allowlist mismatch: {agent_tools}")

policy = next(document for document in kustomize_documents if document and document.get("kind") == "AgentgatewayPolicy")
expression = policy["spec"]["backend"]["mcp"]["authorization"]["policy"]["matchExpressions"][0]
policy_tools = re.findall(r'"([a-z0-9_]+)"', expression)
if policy_tools != expected_tools:
    raise SystemExit(f"agentgateway tool allowlist mismatch: {policy_tools}")

remote_servers = [document for document in kustomize_documents if document and document.get("kind") == "RemoteMCPServer"]
if len(remote_servers) != 1 or remote_servers[0]["metadata"]["name"] != "kubernetes-mcp-fleet-gateway":
    raise SystemExit("direct kagent RemoteMCPServer must be absent")
if remote_servers[0]["spec"]["url"] != expected_gateway_url:
    raise SystemExit(f"gateway URL mismatch: {remote_servers[0]['spec']['url']}")

network_policy = next(
    document for document in kustomize_documents
    if document and document.get("kind") == "NetworkPolicy"
    and document["metadata"]["name"] == "kubernetes-mcp-fleet-allow"
)
cidrs = [entry["ipBlock"]["cidr"] for entry in network_policy["spec"]["egress"][1]["to"]]
if cidrs != expected_cidrs:
    raise SystemExit(f"target API CIDR mismatch: {cidrs}")
for cidr in cidrs:
    network = ipaddress.ip_network(cidr, strict=False)
    if network.prefixlen == 0:
        raise SystemExit(f"default-route egress CIDR is forbidden: {cidr}")
ingress_namespaces = [
    entry["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"]
    for entry in network_policy["spec"]["ingress"][0]["from"]
]
if ingress_namespaces != [expected_gateway_namespace]:
    raise SystemExit(f"MCP ingress must have only the agentgateway namespace: {ingress_namespaces}")
PY

for manifest in "$BUNDLE_DIR/manifests/reader-rbac.yaml" "$tmp_dir/kustomize-rendered.yaml"; do
  kubectl apply --dry-run=client --validate=false -f "$manifest" >/dev/null
done

case "$LIVE_VALIDATE" in
  auto)
    if kubectl --context "$HOST_CONTEXT" --request-timeout=5s get --raw=/readyz >/dev/null 2>&1; then
      LIVE_VALIDATE=1
    else
      LIVE_VALIDATE=0
      echo "LIVE_VALIDATE_SKIPPED host context is unreachable"
    fi
    ;;
  0|1) ;;
  *)
    echo "LIVE_VALIDATE must be auto, 0, or 1" >&2
    exit 1
    ;;
esac
if test "$LIVE_VALIDATE" = "1"; then
  kubectl --context "$HOST_CONTEXT" apply --dry-run=server \
    -f "$tmp_dir/kustomize-rendered.yaml" >/dev/null
fi

"$REPO_ROOT/scripts/public-safe-scan.sh" "$BUNDLE_DIR"
bundle_path=${BUNDLE_DIR#"$REPO_ROOT"/}
git -C "$REPO_ROOT" diff --check -- "$bundle_path"

echo "VERIFY_BUNDLE_OK chart=$CHART_VERSION image=$IMAGE_VERSION live_validate=$LIVE_VALIDATE"
