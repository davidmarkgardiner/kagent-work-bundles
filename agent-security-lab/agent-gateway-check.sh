#!/usr/bin/env bash
set -euo pipefail
 : "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG}" "${LAB_CONTEXT:?Set LAB_CONTEXT}" "${LAB_PRIVATE_DIR:?Set LAB_PRIVATE_DIR}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { echo 'Refusing non-lab context' >&2; exit 1; }
expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
[[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match dedicated cluster' >&2; exit 1; }
K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
work=$(mktemp -d); chmod 700 "$work"
cleanup(){ for pid in "${forward_pid:-}" "${metric_pid:-}"; do if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; done; rm -rf "$work"; }
trap cleanup EXIT
"${K[@]}" -n kagent wait --for=condition=Programmed gateway/tls-agent-gateway --timeout=90s
"${K[@]}" -n kagent rollout status deployment/tls-agent-gateway --timeout=120s
"${K[@]}" -n kagent port-forward svc/tls-agent-gateway 18443:8443 >"$work/forward.log" 2>&1 & forward_pid=$!
for _ in {1..30}; do if grep -q 'Forwarding from' "$work/forward.log"; then break; fi; if ! kill -0 "$forward_pid" 2>/dev/null; then cat "$work/forward.log" >&2; exit 1; fi; sleep 1; done
grep -q 'Forwarding from' "$work/forward.log"
controller=$("${K[@]}" -n kagent get pods -l app.kubernetes.io/component=controller,app.kubernetes.io/name=kagent -o jsonpath='{.items[0].metadata.name}')
"${K[@]}" -n kagent port-forward "pod/$controller" 18590:15090 >"$work/metrics-forward.log" 2>&1 & metric_pid=$!
for _ in {1..30}; do if grep -q 'Forwarding from' "$work/metrics-forward.log"; then break; fi; if ! kill -0 "$metric_pid" 2>/dev/null; then cat "$work/metrics-forward.log" >&2; exit 1; fi; sleep 1; done
grep -q 'Forwarding from' "$work/metrics-forward.log"
cat > "$work/metric.py" <<'PYMETRIC'
import urllib.request
x = urllib.request.urlopen('http://127.0.0.1:18590/stats/prometheus', timeout=8).read().decode()
rows = [s for s in x.splitlines() if s.startswith('istio_tcp_received_bytes_total{') and 'reporter="destination"' in s and 'connection_security_policy="mutual_tls"' in s and 'source_principal="spiffe://cluster.local/ns/kagent/sa/tls-agent-gateway"' in s and 'destination_principal="spiffe://cluster.local/ns/kagent/sa/kagent-controller"' in s]
print(sum(float(s.rsplit(None, 1)[-1]) for s in rows))
PYMETRIC
before=$(python3 "$work/metric.py")
url='https://tls-agent-gateway.kagent.svc.cluster.local:18443/agents/kagent/tls-lab-canary/.well-known/agent-card.json'
# Negative control: a different lab trust root must not validate this listener.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -keyout "$work/wrong.key" -out "$work/wrong.crt" -subj /CN=unrelated-lab-root >/dev/null 2>&1
set +e
curl --noproxy '*' --silent --show-error --cacert "$work/wrong.crt" --resolve tls-agent-gateway.kagent.svc.cluster.local:18443:127.0.0.1 -o /dev/null "$url" 2>"$work/wrong-ca.err"
wrong_ca_rc=$?
set -e
printf 'wrong_ca_curl_exit=%s\n' "$wrong_ca_rc"
[[ "$wrong_ca_rc" == 60 ]] || { echo 'Expected certificate verification failure with an unrelated CA.' >&2; exit 1; }
args=(--noproxy '*' --silent --show-error --cacert "$LAB_PRIVATE_DIR/tls.crt" --resolve tls-agent-gateway.kagent.svc.cluster.local:18443:127.0.0.1 -H 'A2A-Version: 1.0')
missing=$(curl "${args[@]}" -o "$work/missing" -w '%{http_code}' "$url")
printf 'missing_token_status=%s\n' "$missing"
[[ "$missing" == 401 ]]
"${K[@]}" -n kagent create token tls-lab-caller --audience tls-lab-agent --duration 10m > "$work/token"
python3 - "$work/token" "$work/curl-config" <<'PY'
import pathlib,sys
token=pathlib.Path(sys.argv[1]).read_text().strip()
assert token and '\n' not in token
pathlib.Path(sys.argv[2]).write_text('header = "Authorization: Bearer '+token+'"\n')
PY
status=$(curl "${args[@]}" --config "$work/curl-config" -o "$work/card" -w '%{http_code}' "$url")
printf 'authorized_card_status=%s\n' "$status"
[[ "$status" == 200 ]]
python3 - "$work/card" <<'PY'
import json,sys
card=json.load(open(sys.argv[1])); print('card_name=',card.get('name')); assert card.get('name') == 'tls_lab_canary'
PY

# TCP telemetry is periodically flushed; wait for the counter, not another request.
for _ in {1..15}; do
  sleep 2
  after=$(python3 "$work/metric.py")
  if python3 -c 'import sys; sys.exit(0 if float(sys.argv[2]) > float(sys.argv[1]) else 1)' "$before" "$after"; then
    printf 'gateway-to-controller mutual_tls bytes: %s -> %s\n' "$before" "$after"
    echo 'PASS: validated HTTPS, token controls, actual agent card and Gateway-to-controller mTLS.'
    exit 0
  fi
done
printf 'No fresh mTLS bytes observed from expected gateway identity: %s -> %s\n' "$before" "${after:-unknown}" >&2
exit 1
