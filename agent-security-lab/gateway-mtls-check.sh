#!/usr/bin/env bash
set -euo pipefail
: "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG}"
: "${LAB_CONTEXT:?Set LAB_CONTEXT}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { echo 'Refusing non-lab context.' >&2; exit 1; }
expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
[[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match the local dedicated kind cluster.' >&2; exit 1; }
K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
root=$(cd "$(dirname "$0")" && pwd)
"${K[@]}" -n tls-proof wait --for=condition=Ready pod/tls-server --timeout=180s
"${K[@]}" -n tls-plain wait --for=condition=Ready pod/plaintext-client --timeout=180s
[[ "$("${K[@]}" -n tls-proof get peerauthentication tls-server-strict -o jsonpath='{.spec.mtls.mode}')" == STRICT ]] || { echo 'Server must enforce STRICT mTLS.' >&2; exit 1; }
"${K[@]}" apply -f "$root/scenarios/gateway-istio-native.yaml"
"${K[@]}" -n tls-proof wait --for=condition=Programmed gateway/tls-lab-gateway --timeout=180s
"${K[@]}" -n tls-proof rollout status deployment/tls-lab-gateway --timeout=180s
metric='import urllib.request; x=urllib.request.urlopen("http://127.0.0.1:15090/stats/prometheus",timeout=8).read().decode(); rows=[s for s in x.splitlines() if s.startswith("istio_requests_total{") and "reporter=\"destination\"" in s and "connection_security_policy=\"mutual_tls\"" in s and "source_principal=\"spiffe://cluster.local/ns/tls-proof/sa/tls-lab-gateway\"" in s and "destination_principal=\"spiffe://cluster.local/ns/tls-proof/sa/tls-server\"" in s and "response_code=\"200\"" in s]; print(sum(float(s.rsplit(None,1)[-1]) for s in rows))'
before=$("${K[@]}" -n tls-proof exec tls-server -c server -- python -c "$metric")
status=$("${K[@]}" -n tls-plain exec plaintext-client -c client -- python -c 'import urllib.request; r=urllib.request.urlopen("http://tls-lab-gateway.tls-proof.svc.cluster.local:8080/",timeout=10); print(r.status)')
[[ "$status" == 200 ]] || { echo 'Gateway request did not complete.' >&2; exit 1; }
sleep 2
after=$("${K[@]}" -n tls-proof exec tls-server -c server -- python -c "$metric")
python3 -c 'import sys; a,b=map(float,sys.argv[1:]); print(f"gateway-to-server mutual_tls counter: {a} -> {b}"); assert b > a, "No fresh matching gateway mTLS request observed"' "$before" "$after"
echo 'PASS: native Agent Gateway -> STRICT Istio backend uses mTLS with expected peer identities. Test client -> gateway is HTTP.'
