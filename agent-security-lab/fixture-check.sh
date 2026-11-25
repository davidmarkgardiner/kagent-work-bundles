#!/usr/bin/env bash
set -euo pipefail
: "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG}" "${LAB_CONTEXT:?Set LAB_CONTEXT}" "${LAB_PRIVATE_DIR:?Set LAB_PRIVATE_DIR}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { echo 'Refusing non-lab context' >&2; exit 1; }
expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
[[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match dedicated cluster' >&2; exit 1; }
K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
work=$(mktemp -d); chmod 700 "$work"
cleanup(){ for pid in "${f:-}" "${mf:-}"; do if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; done; rm -rf "$work"; }
trap cleanup EXIT
"${K[@]}" -n kagent wait --for=condition=Ready agents.api.kagent.dev/tls-fixture-canary --timeout=120s
"${K[@]}" -n tls-proof rollout status deployment/tls-model-fixture --timeout=120s
[[ "$("${K[@]}" -n tls-proof get peerauthentication tls-model-fixture-strict -o jsonpath='{.spec.mtls.mode}')" == STRICT ]] || { echo 'Fixture server is not STRICT.' >&2; exit 1; }
pod=$("${K[@]}" -n tls-proof get pods -l app=tls-model-fixture -o jsonpath='{.items[0].metadata.name}')
"${K[@]}" -n tls-proof port-forward "pod/$pod" 18592:15090 >"$work/metrics-forward" 2>&1 & mf=$!
"${K[@]}" -n kagent port-forward svc/tls-agent-gateway 18444:8443 >"$work/forward" 2>&1 & f=$!
for _ in {1..30}; do if grep -q 'Forwarding from' "$work/forward" && grep -q 'Forwarding from' "$work/metrics-forward"; then break; fi; kill -0 "$f" && kill -0 "$mf" || { echo 'Port-forward failed' >&2; exit 1; }; sleep 1; done
grep -q 'Forwarding from' "$work/forward"; grep -q 'Forwarding from' "$work/metrics-forward"
cat > "$work/metric.py" <<'PY'
import urllib.request
x = urllib.request.urlopen('http://127.0.0.1:18592/stats/prometheus',timeout=8).read().decode()
rows=[s for s in x.splitlines() if s.startswith('istio_requests_total{') and 'reporter="destination"' in s and 'connection_security_policy="mutual_tls"' in s and 'source_principal="spiffe://cluster.local/ns/tls-proof/sa/tls-lab-gateway"' in s and 'destination_principal="spiffe://cluster.local/ns/tls-proof/sa/tls-model-fixture"' in s and 'response_code="200"' in s]
print(sum(float(s.rsplit(None,1)[-1]) for s in rows))
PY
before=$(python3 "$work/metric.py")
"${K[@]}" -n kagent create token tls-lab-caller --audience tls-lab-agent --duration 10m > "$work/token"
python3 - "$work/token" "$work/curl-config" "$work/payload" <<'PY'
import json,pathlib,sys,uuid
token=pathlib.Path(sys.argv[1]).read_text().strip(); assert token
pathlib.Path(sys.argv[2]).write_text('header = "Authorization: Bearer '+token+'"\n')
json.dump({'jsonrpc':'2.0','id':'fixture-1','method':'SendMessage','params':{'message':{'messageId':str(uuid.uuid4()),'role':'ROLE_USER','parts':[{'text':'Return the fixture response.'}]}}},open(sys.argv[3],'w'))
PY
url='https://tls-agent-gateway.kagent.svc.cluster.local:18444/agents/kagent/tls-fixture-canary'
status=$(curl --noproxy '*' --silent --show-error --max-time 180 --cacert "$LAB_PRIVATE_DIR/tls.crt" --resolve tls-agent-gateway.kagent.svc.cluster.local:18444:127.0.0.1 --config "$work/curl-config" -H 'A2A-Version: 1.0' -H 'Content-Type: application/json' --data-binary @"$work/payload" -o "$work/result" -w '%{http_code}' "$url")
[[ "$status" == 200 ]] || { echo "Fixture task HTTP status: $status" >&2; exit 1; }
python3 - "$work/result" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); task=x.get('result',{}).get('task',{}); state=task.get('status',{}).get('state'); texts=[p.get('text') for a in task.get('artifacts',[]) for p in a.get('parts',[])]; print('task_state=',state,'fixture_response=',texts); assert state=='TASK_STATE_COMPLETED' and 'LAB_FIXTURE_OK' in texts
PY
# Counter evidence is separate from the task receipt; this isolated test must have no concurrent fixture calls.
for _ in {1..15}; do
  sleep 2
  after=$(python3 "$work/metric.py")
  if python3 -c 'import sys; sys.exit(0 if float(sys.argv[2]) > float(sys.argv[1]) else 1)' "$before" "$after"; then
    printf 'fixture gateway-to-model mutual_tls count: %s -> %s\n' "$before" "$after"
    echo 'PASS: synthetic model task completed; fixture backend received mTLS from Gateway.'
    echo 'Boundary: the model configuration uses HTTP from Substrate egress to the model Gateway.'
    exit 0
  fi
done
echo 'No fresh Gateway-to-fixture mTLS metric observed.' >&2
exit 1
