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

mcp_image_dir="$BUNDLE_DIR/mcp-image"
for required_image_contract in \
  'quay.io/containers/kubernetes_mcp_server:v0.0.66' \
  'kubelogin-linux-amd64.zip' \
  'ebaeff02aa899c5cae6a2b954b64fc02738185319df2570f7dc053451efa4b2f' \
  'bin/linux_amd64/kubelogin' \
  'v0.0.66-kubelogin-v0.2.19'; do
  rg -q --fixed-strings "$required_image_contract" "$mcp_image_dir/README.md" || {
    echo "MCP image guide is missing pinned contract: $required_image_contract" >&2
    exit 1
  }
done
for required_dockerfile_fragment in \
  'COPY --chmod=0555 kubelogin /usr/local/bin/kubelogin' \
  'RUN /usr/local/bin/kubelogin --version'; do
  rg -q --fixed-strings "$required_dockerfile_fragment" "$mcp_image_dir/Dockerfile" || {
    echo "MCP image Dockerfile is missing: $required_dockerfile_fragment" >&2
    exit 1
  }
done
if rg -n '(^|[[:space:]])(curl|wget|dnf|microdnf|yum|apt(-get)?|apk)([[:space:]]|$)' \
  "$mcp_image_dir/Dockerfile" >/dev/null; then
  echo "MCP image Dockerfile must not download or install packages" >&2
  exit 1
fi

refresh_script="$BUNDLE_DIR/scripts/refresh-aks-kubeconfig-job.sh"
if rg -n --fixed-strings -- '--admin' "$refresh_script" >/dev/null; then
  echo "AKS credential Job must never request admin credentials" >&2
  exit 1
fi
for required_fragment in \
  'az aks list' \
  'az aks get-credentials' \
  'kubelogin convert-kubeconfig -l workloadidentity' \
  'kubectl replace -f -' \
  'auth can-i get secrets'; do
  rg -q --fixed-strings "$required_fragment" "$refresh_script" || {
    echo "AKS credential Job contract is missing: $required_fragment" >&2
    exit 1
  }
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
  --set-string fullnameOverride="$MCP_NAME" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${tool_set_args[@]}" >/dev/null
helm template "$MCP_NAME" "$chart_dir" \
  --namespace "$HOST_NAMESPACE" -f "$BUNDLE_DIR/values.yaml" \
  --set-string fullnameOverride="$MCP_NAME" \
  --set-string kubeconfigSecretName=kubernetes-mcp-fleet-kubeconfig-example \
  --set-string image.registry="$IMAGE_REGISTRY" \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.version="$IMAGE_VERSION" \
  "${tool_set_args[@]}" >"$tmp_dir/helm-rendered.yaml"

expected_image="$IMAGE_REGISTRY/$IMAGE_REPOSITORY:$IMAGE_VERSION"
python3 - "$tmp_dir/helm-rendered.yaml" "$tmp_dir/kustomize-rendered.yaml" \
  "$expected_image" "$TOOL_ALLOWLIST" "$TARGET_API_CIDRS" \
  "$AGENTGATEWAY_MCP_URL" "$AGENTGATEWAY_NAMESPACE" \
  "$MCP_NAME" "$KAGENT_AGENT_NAME" "$REMOTE_MCP_NAME" \
  "$AGENTGATEWAY_MCP_PATH" "$KUBECONFIG_SECRET_NAME" \
  "$CREDENTIAL_REFRESH_NAME" "$CREDENTIAL_REFRESH_CONFIG_NAME" \
  "$CREDENTIAL_REFRESH_SCRIPT_CONFIG_NAME" "$CREDENTIAL_REFRESH_IMAGE" \
  "$CREDENTIAL_REFRESH_SUSPEND" "$AKS_MCP_WORKLOAD_NAMESPACE" \
  "$AKS_MCP_SERVICE_ACCOUNT" "$MCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT" \
  "$AKS_MCP_UAMI_CLIENT_ID" "$CREDENTIAL_REFRESH_CRON_MINUTE" \
  "$CREDENTIAL_REFRESH_CRON_HOUR" "$AZURE_IDENTITY_EGRESS_CIDRS" <<'PY'
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
expected_mcp_name = sys.argv[8]
expected_agent_name = sys.argv[9]
expected_remote_name = sys.argv[10]
expected_gateway_path = sys.argv[11]
expected_secret_name = sys.argv[12]
expected_refresh_name = sys.argv[13]
expected_refresh_config = sys.argv[14]
expected_refresh_script = sys.argv[15]
expected_refresh_image = sys.argv[16]
expected_refresh_suspend = sys.argv[17] == "true"
expected_refresh_namespace = sys.argv[18]
expected_refresh_sa = sys.argv[19]
expected_mcp_sa = sys.argv[20]
expected_uami_client_id = sys.argv[21]
expected_cron_minute = sys.argv[22]
expected_cron_hour = sys.argv[23]
expected_identity_cidrs = sys.argv[24].split(",")

rendered_text = open(sys.argv[2], encoding="utf-8").read()
if "REPLACE" in rendered_text or "{{" in rendered_text:
    raise SystemExit("Kustomize output contains an unresolved placeholder")

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
if deployment["metadata"]["name"] != expected_mcp_name:
    raise SystemExit(f"Helm workload name mismatch: {deployment['metadata']['name']}")
if deployment["spec"]["template"]["metadata"]["labels"].get("azure.workload.identity/use") != "true":
    raise SystemExit("MCP pod is missing the Azure Workload Identity label")
secret_volume = next(v for v in deployment["spec"]["template"]["spec"]["volumes"] if v["name"] == "fleet-kubeconfig")
if secret_volume["secret"].get("items") != [{"key": "kubeconfig", "path": "kubeconfig"}]:
    raise SystemExit("MCP volume must mount only the active kubeconfig key")

agent = next(document for document in kustomize_documents if document and document.get("kind") == "Agent")
if agent["metadata"]["name"] != expected_agent_name:
    raise SystemExit(f"Agent name mismatch: {agent['metadata']['name']}")
agent_tools = agent["spec"]["declarative"]["tools"][0]["mcpServer"]["toolNames"]
if agent_tools != expected_tools:
    raise SystemExit(f"Agent tool allowlist mismatch: {agent_tools}")

policy = next(document for document in kustomize_documents if document and document.get("kind") == "AgentgatewayPolicy")
expression = policy["spec"]["backend"]["mcp"]["authorization"]["policy"]["matchExpressions"][0]
policy_tools = re.findall(r'"([a-z0-9_]+)"', expression)
if policy_tools != expected_tools:
    raise SystemExit(f"agentgateway tool allowlist mismatch: {policy_tools}")

remote_servers = [document for document in kustomize_documents if document and document.get("kind") == "RemoteMCPServer"]
if len(remote_servers) != 1 or remote_servers[0]["metadata"]["name"] != expected_remote_name:
    raise SystemExit("direct kagent RemoteMCPServer must be absent")
if remote_servers[0]["spec"]["url"] != expected_gateway_url:
    raise SystemExit(f"gateway URL mismatch: {remote_servers[0]['spec']['url']}")
if agent["spec"]["declarative"]["tools"][0]["mcpServer"]["name"] != expected_remote_name:
    raise SystemExit("Agent does not reference the rendered RemoteMCPServer name")

backend = next(document for document in kustomize_documents if document and document.get("kind") == "AgentgatewayBackend")
route = next(document for document in kustomize_documents if document and document.get("kind") == "HTTPRoute")
gateway_policy = next(document for document in kustomize_documents if document and document.get("kind") == "AgentgatewayPolicy")
if backend["metadata"]["name"] != expected_mcp_name or backend["spec"]["mcp"]["targets"][0]["name"] != expected_mcp_name:
    raise SystemExit("Agentgateway backend name mismatch")
if backend["spec"]["mcp"]["targets"][0]["static"]["host"].split(".", 1)[0] != expected_mcp_name:
    raise SystemExit("Agentgateway backend host is not derived from MCP_NAME")
if route["metadata"]["name"] != expected_mcp_name or route["spec"]["rules"][0]["matches"][0]["path"]["value"] != expected_gateway_path:
    raise SystemExit("HTTPRoute name or path mismatch")
if gateway_policy["metadata"]["name"] != expected_mcp_name or gateway_policy["spec"]["targetRefs"][0]["name"] != expected_mcp_name:
    raise SystemExit("Agentgateway policy target mismatch")

credential_secret = next(document for document in kustomize_documents if document and document.get("kind") == "Secret")
if credential_secret["metadata"]["name"] != expected_secret_name or credential_secret.get("data"):
    raise SystemExit("credential Secret must be a named, initially empty publisher target")
mcp_service_account = next(document for document in kustomize_documents if document and document.get("kind") == "ServiceAccount")
if mcp_service_account["metadata"]["name"] != expected_mcp_sa:
    raise SystemExit("MCP Workload Identity ServiceAccount name mismatch")
if mcp_service_account["metadata"]["annotations"].get("azure.workload.identity/client-id") != expected_uami_client_id:
    raise SystemExit("MCP ServiceAccount UAMI annotation mismatch")

refresh = next(document for document in kustomize_documents if document and document.get("kind") == "CronJob")
refresh_pod = refresh["spec"]["jobTemplate"]["spec"]["template"]
refresh_container = refresh_pod["spec"]["containers"][0]
if refresh["metadata"]["name"] != expected_refresh_name or refresh["metadata"]["namespace"] != expected_refresh_namespace:
    raise SystemExit("credential CronJob name or namespace mismatch")
if refresh["spec"]["schedule"] != f"{expected_cron_minute} {expected_cron_hour} * * *" or refresh["spec"]["suspend"] is not expected_refresh_suspend:
    raise SystemExit("credential CronJob schedule or suspend state mismatch")
if refresh_pod["spec"]["serviceAccountName"] != expected_refresh_sa:
    raise SystemExit("credential CronJob does not reuse the configured AKS-MCP ServiceAccount")
if refresh_pod["metadata"]["labels"].get("azure.workload.identity/use") != "true":
    raise SystemExit("credential CronJob is missing the Workload Identity label")
if refresh_container["image"] != expected_refresh_image:
    raise SystemExit("credential CronJob image mismatch")
if refresh_container["envFrom"][0]["configMapRef"]["name"] != expected_refresh_config:
    raise SystemExit("credential CronJob values ConfigMap mismatch")
if refresh_pod["spec"]["volumes"][0]["configMap"]["name"] != expected_refresh_script:
    raise SystemExit("credential CronJob script ConfigMap mismatch")

publisher_role = next(document for document in kustomize_documents if document and document.get("kind") == "Role")
publisher_binding = next(document for document in kustomize_documents if document and document.get("kind") == "RoleBinding")
if publisher_role["rules"][0] != {"apiGroups": [""], "resourceNames": [expected_secret_name], "resources": ["secrets"], "verbs": ["get", "update"]}:
    raise SystemExit("credential publisher Secret RBAC widened or drifted")
if publisher_role["rules"][1]["resourceNames"] != [expected_mcp_name] or publisher_role["rules"][1]["verbs"] != ["get", "patch"]:
    raise SystemExit("credential publisher Deployment RBAC widened or drifted")
subject = publisher_binding["subjects"][0]
if subject["name"] != expected_refresh_sa or subject["namespace"] != expected_refresh_namespace:
    raise SystemExit("credential publisher binding subject mismatch")

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
identity_cidrs = [entry["ipBlock"]["cidr"] for entry in network_policy["spec"]["egress"][2]["to"]]
if identity_cidrs != expected_identity_cidrs:
    raise SystemExit(f"identity egress CIDR mismatch: {identity_cidrs}")
for cidr in identity_cidrs:
    if ipaddress.ip_network(cidr, strict=False).prefixlen == 0:
        raise SystemExit(f"default-route identity egress CIDR is forbidden: {cidr}")
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
