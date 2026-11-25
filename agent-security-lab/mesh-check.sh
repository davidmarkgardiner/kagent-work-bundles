#!/usr/bin/env bash
set -euo pipefail
: "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG to the dedicated lab kubeconfig}"
: "${LAB_CONTEXT:?Set LAB_CONTEXT to the dedicated kind context}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { printf 'Refusing non-lab context\n' >&2; exit 1; }
verify_target() {
  local expected actual
  expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
  actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
  [[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match the local dedicated kind cluster.' >&2; exit 1; }
}

K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
root=$(cd "$(dirname "$0")" && pwd)
verify_target
"${K[@]}" get --raw=/readyz >/dev/null
"${K[@]}" apply -f "$root/scenarios/mesh-mtls.yaml"
"${K[@]}" -n tls-proof wait --for=condition=Ready pod/tls-server pod/tls-client --timeout=180s
"${K[@]}" -n tls-plain wait --for=condition=Ready pod/plaintext-client --timeout=180s
restore() { "${K[@]}" -n tls-proof patch peerauthentication tls-server-strict --type merge -p '{"spec":{"mtls":{"mode":"STRICT"}}}' >/dev/null; }
trap restore EXIT
request='import urllib.request; r=urllib.request.urlopen("http://tls-server.tls-proof.svc.cluster.local:8080/",timeout=8); print(r.status)'
metric='import urllib.request; x=urllib.request.urlopen("http://127.0.0.1:15090/stats/prometheus",timeout=8).read().decode(); rows=[s for s in x.splitlines() if s.startswith("istio_requests_total{") and "reporter=\"destination\"" in s and "connection_security_policy=\"mutual_tls\"" in s and "source_workload=\"tls-client\"" in s and "destination_workload=\"tls-server\"" in s and "source_principal=\"spiffe://cluster.local/ns/tls-proof/sa/tls-client\"" in s and "destination_principal=\"spiffe://cluster.local/ns/tls-proof/sa/tls-server\"" in s and "response_code=\"200\"" in s]; print(sum(float(s.rsplit(None,1)[-1]) for s in rows))'
before=$("${K[@]}" -n tls-proof exec tls-server -c server -- python -c "$metric")
mesh=$("${K[@]}" -n tls-proof exec tls-client -c client -- python -c "$request")
[[ "$mesh" == 200 ]] || { printf 'Mesh request failed: %s\n' "$mesh" >&2; exit 1; }
sleep 2
after=$("${K[@]}" -n tls-proof exec tls-server -c server -- python -c "$metric")
python3 -c 'import sys; a,b=map(float,sys.argv[1:]); print(f"destination mutual_tls counter: {a} -> {b}"); assert b > a, "No matching fresh mTLS request observed"' "$before" "$after"
reject_test=$'import urllib.request\ntry:\n urllib.request.urlopen("http://tls-server.tls-proof.svc.cluster.local:8080/",timeout=8)\nexcept ConnectionResetError:\n print("strict_connection_reset")\nelse:\n raise SystemExit("plaintext unexpectedly accepted")'
"${K[@]}" -n tls-plain exec plaintext-client -c client -- python -c "$reject_test"
"${K[@]}" -n tls-proof patch peerauthentication tls-server-strict --type merge -p '{"spec":{"mtls":{"mode":"PERMISSIVE"}}}' >/dev/null
sleep 5
plain=$("${K[@]}" -n tls-plain exec plaintext-client -c client -- python -c "$request")
[[ "$plain" == 200 ]] || { printf 'Plaintext control failed: %s\n' "$plain" >&2; exit 1; }
restore
sleep 5
"${K[@]}" -n tls-plain exec plaintext-client -c client -- python -c "$reject_test"
printf 'PASS: mTLS 200; destination metric reports mutual_tls; plaintext rejected/allowed/rejected under strict/permissive/strict.\n'
