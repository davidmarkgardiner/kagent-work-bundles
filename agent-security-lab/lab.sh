#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
# This local, version-controlled file contains version pins only.
# shellcheck source=versions.env
source "$root/versions.env"
: "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG to the dedicated lab kubeconfig}"
: "${LAB_CONTEXT:?Set LAB_CONTEXT to kind-agent-tls}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { echo 'Refusing non-lab context.' >&2; exit 1; }
verify_target() {
  local expected actual
  expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
  actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
  [[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match the local dedicated kind cluster.' >&2; exit 1; }
}

K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
H=(helm --kubeconfig "$LAB_KUBECONFIG" --kube-context "$LAB_CONTEXT")
case "${1:-}" in
  create)
    [[ "${2:-}" == '--apply' ]] || { echo 'Create the dedicated kind-agent-tls cluster; pass --apply to execute.'; exit 0; }
    ! kind get clusters | grep -qx 'agent-tls' || { echo 'Cluster already exists; inspect it rather than replacing it.' >&2; exit 1; }
    kind create cluster --name agent-tls --image "$KIND_NODE_IMAGE" --kubeconfig "$LAB_KUBECONFIG" --wait 180s
    ;;
  status)
    verify_target
    "${K[@]}" get --raw=/readyz
    "${K[@]}" get nodes
    "${K[@]}" get pods -A
    ;;
  fix-kind-dns)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Update only this kind node to the VM upstream DNS and restart its CoreDNS; pass --apply to execute.'; exit 0; }
    [[ -r /run/systemd/resolve/resolv.conf ]] || { echo 'VM upstream resolver file is unavailable.' >&2; exit 1; }
    grep -Eq '^nameserver ([1-9][0-9]*\.|[a-fA-F0-9]*:)' /run/systemd/resolve/resolv.conf || { echo 'No usable upstream DNS found.' >&2; exit 1; }
    docker exec -i agent-tls-control-plane sh -c 'cat > /etc/resolv.conf' < /run/systemd/resolve/resolv.conf
    "${K[@]}" -n kube-system rollout restart deployment/coredns
    "${K[@]}" -n kube-system rollout status deployment/coredns --timeout=120s
    ;;
  install-mesh)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Install Istio only into kind-agent-tls; pass --apply to execute.'; exit 0; }
    "${K[@]}" get --raw=/readyz >/dev/null
    "${H[@]}" upgrade --install istio-base base --repo https://blob.istio.io/istio-release/charts --version "$ISTIO_VERSION" --namespace istio-system --create-namespace --wait --timeout 5m
    "${H[@]}" upgrade --install istiod istiod --repo https://blob.istio.io/istio-release/charts --version "$ISTIO_VERSION" --namespace istio-system --wait --timeout 5m
    ;;
  install-kagent)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Install release-matched kagent and Substrate with an Ollama placeholder into the dedicated cluster; pass --apply to execute.'; exit 0; }
    [[ "$(kagent version | python3 -c 'import json,sys; print(json.load(sys.stdin).get("kagent_version", ""))')" == "$KAGENT_VERSION" ]] || { echo 'kagent CLI version does not match the lock.' >&2; exit 1; }
    "${K[@]}" get --raw=/readyz >/dev/null
    [[ "$(kubectl --kubeconfig "$LAB_KUBECONFIG" config current-context)" == "$LAB_CONTEXT" ]] || { echo 'Installer kubeconfig current context does not match the dedicated lab.' >&2; exit 1; }
    if "${H[@]}" -n kagent status kagent >/dev/null 2>&1; then
      echo 'kagent release already exists; inspect it instead of rerunning the installer and replacing model configuration.' >&2
      exit 1
    fi
    # The installer requires this field even for the local Ollama profile. This is not a working provider credential.
    KUBECONFIG="$LAB_KUBECONFIG" OLLAMA_API_KEY=lab-placeholder kagent install --provider Ollama --profile minimal --namespace kagent
    ;;
  install-gateway)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Install Gateway API and Agent Gateway into the dedicated cluster; pass --apply to execute.'; exit 0; }
    "${K[@]}" get --raw=/readyz >/dev/null
    api_file=$(mktemp)
    trap 'rm -f "$api_file"' EXIT
    curl -fsSL "https://github.com/kubernetes-sigs/gateway-api/releases/download/v${GATEWAY_API_VERSION}/standard-install.yaml" -o "$api_file"
    printf '%s  %s\n' "$GATEWAY_MANIFEST_SHA256" "$api_file" | sha256sum -c -
    "${K[@]}" apply --server-side -f "$api_file"
    rm -f "$api_file"
    trap - EXIT
    "${H[@]}" upgrade --install agentgateway-crds oci://cr.agentgateway.dev/charts/agentgateway-crds --version "$AGENTGATEWAY_VERSION" --namespace agentgateway-system --create-namespace --wait --timeout 5m
    "${H[@]}" upgrade --install agentgateway oci://cr.agentgateway.dev/charts/agentgateway --version "$AGENTGATEWAY_VERSION" --namespace agentgateway-system --wait --timeout 5m
    ;;
  install-kro)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Install KRO into the dedicated cluster; pass --apply to execute.'; exit 0; }
    "${K[@]}" get --raw=/readyz >/dev/null
    "${H[@]}" upgrade --install kro oci://registry.k8s.io/kro/charts/kro --version "$KRO_VERSION" --namespace kro-system --create-namespace --wait --timeout 5m
    ;;
  kro-canary)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Create a tool-free KRO-composed 1.x canary; pass --apply to execute.'; exit 0; }
    "${K[@]}" apply --dry-run=server -f "$root/scenarios/kro-native-canary.yaml"
    "${K[@]}" apply -f "$root/scenarios/kro-native-canary.yaml"
    "${K[@]}" wait --for=condition=Ready resourcegraphdefinition/agent-security-lab-canary --timeout=120s
    "${K[@]}" apply -f "$root/scenarios/kro-native-canary-instance.yaml"
    "${K[@]}" -n kagent wait --for=condition=Ready agentsecuritycanary.lab.example/tls-lab-canary --timeout=180s
    "${K[@]}" -n kagent wait --for=condition=Ready agents.api.kagent.dev/tls-lab-canary --timeout=300s
    ;;
  controller-mesh)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Inject an Istio sidecar into the dedicated lab kagent controller only; pass --apply to execute.'; exit 0; }
    "${K[@]}" -n kagent patch deployment kagent-controller --type merge -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
    "${K[@]}" -n kagent rollout status deployment/kagent-controller --timeout=180s
    ;;
  agent-gateway-setup)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Create a lab-only HTTPS Agent Gateway and caller policy; pass --apply to execute.'; exit 0; }
    exec "$root/agent-gateway-setup.sh"
    ;;
  agent-gateway-check)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Run one TLS-protected card lookup with missing/valid token controls; pass --apply to execute.'; exit 0; }
    exec "$root/agent-gateway-check.sh"
    ;;
  fixture-setup)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Create the local deterministic model fixture and 1.x KRO agent; pass --apply to execute.'; exit 0; }
    exec "$root/fixture-setup.sh"
    ;;
  fixture-check)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Run one synthetic A2A task against the local model fixture; pass --apply to execute.'; exit 0; }
    exec "$root/fixture-check.sh"
    ;;
  mesh-test)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Run the dedicated mesh test, including a temporary permissive control; pass --apply to execute.'; exit 0; }
    exec "$root/mesh-check.sh"
    ;;
  gateway-mtls-test)
    verify_target
    [[ "${2:-}" == '--apply' ]] || { echo 'Run native Agent Gateway to STRICT mesh backend test; pass --apply to execute.'; exit 0; }
    exec "$root/gateway-mtls-check.sh"
    ;;
  destroy)
    verify_target
    [[ "${2:-}" == '--destroy-agent-tls' ]] || { echo 'Destructive: removes kind cluster agent-tls and its data. Pass --destroy-agent-tls only after explicit user authorization for this exact cluster.'; exit 1; }
    kind delete cluster --name agent-tls --kubeconfig "$LAB_KUBECONFIG"
    ;;
  *) echo 'Usage: lab.sh create|status|fix-kind-dns|install-mesh|install-kagent|install-gateway|install-kro|kro-canary|controller-mesh|agent-gateway-setup|agent-gateway-check|fixture-setup|fixture-check|mesh-test|gateway-mtls-test|destroy [explicit flag]' >&2; exit 2 ;;
esac
