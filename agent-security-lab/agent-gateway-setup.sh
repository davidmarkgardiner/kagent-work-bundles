#!/usr/bin/env bash
set -euo pipefail
: "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG}" "${LAB_CONTEXT:?Set LAB_CONTEXT}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { echo 'Refusing non-lab context' >&2; exit 1; }
expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
[[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match dedicated cluster' >&2; exit 1; }
K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
root=$(cd "$(dirname "$0")" && pwd)
private="${LAB_PRIVATE_DIR:?Set LAB_PRIVATE_DIR to a private directory}"
umask 077
mkdir -p "$private"
if [[ ! -e "$private/tls.key" && ! -e "$private/tls.crt" ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 7 -keyout "$private/tls.key" -out "$private/tls.crt" -subj /CN=tls-agent-gateway.kagent.svc.cluster.local -addext subjectAltName=DNS:tls-agent-gateway.kagent.svc.cluster.local >/dev/null 2>&1
fi
[[ -s "$private/tls.key" && -s "$private/tls.crt" ]] || { echo 'Incomplete lab TLS certificate; stop.' >&2; exit 1; }
"${K[@]}" -n kagent create secret tls tls-agent-gateway-cert --cert="$private/tls.crt" --key="$private/tls.key" --dry-run=client -o yaml | "${K[@]}" apply -f -
# No route is created until the listener-level JWT policy is accepted and attached.
"${K[@]}" apply -f "$root/scenarios/agent-gateway-route.yaml"
python3 "$root/render-caller-policy.py" "$LAB_KUBECONFIG" "$LAB_CONTEXT" | "${K[@]}" apply -f -
# Agentgateway reports conditions under status.ancestors, not status.conditions.
ready=0
for _ in {1..30}; do
  if "${K[@]}" -n kagent get agentgatewaypolicy tls-agent-caller-auth -o json | python3 -c 'import json,sys; x=json.load(sys.stdin); gen=x["metadata"]["generation"]; a=[a for a in x.get("status",{}).get("ancestors",[]) if a.get("ancestorRef",{}).get("name")=="tls-agent-gateway" and a.get("ancestorRef",{}).get("namespace","kagent")=="kagent" and a.get("controllerName")=="agentgateway.dev/agentgateway"]; ok=any(all(any(c.get("type")==t and c.get("status")=="True" and c.get("observedGeneration")==gen for c in z.get("conditions",[])) for t in ("Accepted","Attached")) for z in a); sys.exit(0 if ok else 1)'; then ready=1; break; fi
  sleep 2
done
[[ "$ready" == 1 ]] || { echo 'Gateway policy did not become accepted and attached for its current generation.' >&2; exit 1; }
"${K[@]}" apply -f "$root/scenarios/agent-gateway-route-binding.yaml"
