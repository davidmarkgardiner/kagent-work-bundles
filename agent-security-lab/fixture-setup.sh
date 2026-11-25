#!/usr/bin/env bash
set -euo pipefail
: "${LAB_KUBECONFIG:?Set LAB_KUBECONFIG}" "${LAB_CONTEXT:?Set LAB_CONTEXT}"
[[ "$LAB_CONTEXT" == kind-agent-tls ]] || { echo 'Refusing non-lab context' >&2; exit 1; }
expected=$(kind get kubeconfig --name agent-tls | kubectl config view --raw --kubeconfig /dev/stdin -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
actual=$(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT" config view --raw --minify -o jsonpath='{.clusters[0].cluster.server}{" "}{.clusters[0].cluster.certificate-authority-data}')
[[ -n "$expected" && "$actual" == "$expected" ]] || { echo 'Kubeconfig does not match dedicated cluster' >&2; exit 1; }
K=(kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$LAB_CONTEXT")
root=$(cd "$(dirname "$0")" && pwd)
"${K[@]}" -n tls-proof get gateway tls-lab-gateway >/dev/null
# This literal is a public, non-functional fixture placeholder, not a provider credential.
"${K[@]}" -n kagent create secret generic tls-lab-fixture-model-key --from-literal=key=lab-placeholder --dry-run=client -o yaml | "${K[@]}" apply -f -
"${K[@]}" apply --dry-run=server -f "$root/scenarios/model-fixture.yaml" -f "$root/scenarios/model-fixture-config.yaml" -f "$root/scenarios/kro-fixture-agent.yaml"
"${K[@]}" apply -f "$root/scenarios/model-fixture.yaml" -f "$root/scenarios/model-fixture-config.yaml" -f "$root/scenarios/kro-fixture-agent.yaml"
"${K[@]}" -n tls-proof rollout status deployment/tls-model-fixture --timeout=180s
"${K[@]}" wait --for=condition=Ready resourcegraphdefinition/agent-security-lab-fixture --timeout=120s
"${K[@]}" apply -f "$root/scenarios/kro-fixture-instance.yaml"
"${K[@]}" -n kagent wait --for=condition=Ready agentfixturecanary.lab.example/tls-fixture-canary --timeout=180s
"${K[@]}" -n kagent wait --for=condition=Ready agents.api.kagent.dev/tls-fixture-canary --timeout=300s
"${K[@]}" -n kagent get agentgatewaypolicy tls-agent-caller-auth -o json | python3 -c 'import json,sys; x=json.load(sys.stdin); gen=x["metadata"]["generation"]; a=[a for a in x.get("status",{}).get("ancestors",[]) if a.get("ancestorRef",{}).get("name")=="tls-agent-gateway" and a.get("controllerName")=="agentgateway.dev/agentgateway"]; assert any(all(any(c.get("type")==t and c.get("status")=="True" and c.get("observedGeneration")==gen for c in z.get("conditions",[])) for t in ("Accepted","Attached")) for z in a), "Caller policy is not accepted and attached"'
"${K[@]}" apply -f "$root/scenarios/agent-fixture-route.yaml"
