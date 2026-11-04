#!/usr/bin/env bash
# Restore a namespace revision, then recreate one Deployment's Pods via its template.
set -euo pipefail
umask 077
if [[ $# -lt 6 || $# -gt 7 ]]; then
  echo "Usage: $0 CONTEXT NAMESPACE DEPLOYMENT BAD_REV GOOD_REV EXPECTED_PROXY_IMAGE [--apply]" >&2
  exit 2
fi
ctx=$1 ns=$2 deploy=$3 bad=$4 good=$5 image=$6 mode=${7:---plan}
[[ "$mode" == --plan || "$mode" == --apply ]] || exit 2
[[ -n "$ctx" && -n "$ns" && -n "$deploy" && -n "$bad" && -n "$good" && -n "$image" && "$bad" != "$good" ]] || exit 2
command -v jq >/dev/null
command -v kubectl >/dev/null
k=(kubectl --context "$ctx" --request-timeout=30s)
out=$(mktemp -d "${TMPDIR:-/tmp}/istio-rollback.XXXXXXXX")
echo "Private evidence directory: $out"
trap 'rc=$?; if [[ $rc -ne 0 ]]; then echo "STOPPED (exit $rc). Inspect evidence at $out. No automatic retry or undo." >&2; fi' EXIT
"${k[@]}" get namespace "$ns" -o json > "$out/namespace-before.json"
"${k[@]}" -n "$ns" get deployment "$deploy" -o json > "$out/deployment-before.json"
jq -e --arg bad "$bad" --arg good "$good" '
  (.metadata.labels["istio.io/rev"] == $bad or .metadata.labels["istio.io/rev"] == $good)
  and (.metadata.labels["istio-injection"] == null)
  and (.metadata.labels["istio.io/dataplane-mode"] != "ambient")
' "$out/namespace-before.json" >/dev/null || {
  echo "Namespace must use the expected bad/good revision, without legacy injection or ambient labels." >&2; exit 1;
}
jq -e --arg bad "$bad" --arg good "$good" '
  (.spec.paused != true) and ((.spec.replicas // 1) > 0)
  and ((.spec.strategy.type // "RollingUpdate") == "RollingUpdate")
  and (.spec.template.spec.hostNetwork != true)
  and (.spec.template.metadata.labels["sidecar.istio.io/inject"] != "false")
  and (.spec.template.metadata.annotations["sidecar.istio.io/inject"] != "false")
  and (.spec.template.metadata.annotations["sidecar.istio.io/proxyImage"] == null)
  and (.spec.template.metadata.labels["istio.io/rev"] as $r | $r == null or $r == $bad or $r == $good)
  and ([.spec.template.spec.containers[], (.spec.template.spec.initContainers // [])[]]
    | all(.name != "istio-proxy" and .name != "istio-init"))
' "$out/deployment-before.json" >/dev/null || {
  echo "Unsupported Deployment: inspect injection overrides, manual sidecars, revision, strategy, replicas or pause state." >&2; exit 1;
}
jq --arg good "$good" '[
  {op:"test",path:"/metadata/resourceVersion",value:.metadata.resourceVersion},
  {op:"replace",path:"/metadata/labels/istio.io~1rev",value:$good}
]' "$out/namespace-before.json" > "$out/namespace-patch.json"
jq --arg good "$good" --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  [{op:"test",path:"/metadata/resourceVersion",value:.metadata.resourceVersion}]
  + (if .spec.template.metadata.labels["istio.io/rev"] != null then
      [{op:"replace",path:"/spec/template/metadata/labels/istio.io~1rev",value:$good}] else [] end)
  + [{op:"add",path:"/spec/template/metadata/annotations",
      value:((.spec.template.metadata.annotations // {}) + {"kubectl.kubernetes.io/restartedAt":$now})}]
' "$out/deployment-before.json" > "$out/deployment-patch.json"
"${k[@]}" patch namespace "$ns" --type=json --patch-file "$out/namespace-patch.json" --dry-run=server -o json > "$out/namespace-dry-run.json"
jq -e --arg good "$good" '.metadata.labels["istio.io/rev"] == $good' "$out/namespace-dry-run.json" >/dev/null || {
  echo "Admission rewrote the namespace revision. Stop the mutator first." >&2; exit 1;
}
if [[ "$mode" != --apply ]]; then
  echo "PLAN ONLY: namespace $ns -> $good; then inject a dry-run Pod and roll deployment/$deploy only."
  echo "The namespace change affects future Pods from ALL workloads in this namespace."
  echo "Before --apply: stop admission AND mutate-existing rules via GitOps; verify old istiod/injector health and GitOps desired labels."
  echo "The live Pod injection check happens after the namespace label is restored, before the Deployment changes."
  exit 0
fi
"${k[@]}" patch namespace "$ns" --type=json --patch-file "$out/namespace-patch.json" -o json > "$out/namespace-after.json"
jq -e --arg good "$good" '.metadata.labels["istio.io/rev"] == $good' "$out/namespace-after.json" >/dev/null
jq --arg ns "$ns" --arg good "$good" '
  {apiVersion:"v1",kind:"Pod",metadata:{generateName:"istio-rollback-probe-",namespace:$ns,
    labels:((.spec.template.metadata.labels // {}) + {"istio.io/rev":$good}),
    annotations:(.spec.template.metadata.annotations // {})},spec:.spec.template.spec}
' "$out/deployment-before.json" > "$out/probe.json"
"${k[@]}" -n "$ns" create --dry-run=server -f "$out/probe.json" -o json > "$out/probe-admitted.json"
jq -e --arg image "$image" '
  [.spec.containers[], (.spec.initContainers // [])[]] | any(.name == "istio-proxy" and .image == $image)
' "$out/probe-admitted.json" >/dev/null || {
  echo "Dry-run Pod did not receive the EXACT expected proxy image. Namespace may be restored; Deployment was NOT changed." >&2; exit 1;
}
"${k[@]}" -n "$ns" patch deployment "$deploy" --type=json --patch-file "$out/deployment-patch.json" --dry-run=server -o json > "$out/deployment-dry-run.json"
jq -e --arg good "$good" --slurpfile before "$out/deployment-before.json" '
  (.spec.template.metadata.labels["istio.io/rev"] as $r | $r == null or $r == $good)
  and (.spec.template.spec == $before[0].spec.template.spec)
  and (.spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"] != null)
' "$out/deployment-dry-run.json" >/dev/null || {
  echo "Admission changed the Deployment unexpectedly. Deployment was NOT changed." >&2; exit 1;
}
"${k[@]}" -n "$ns" patch deployment "$deploy" --type=json --patch-file "$out/deployment-patch.json" -o json > "$out/deployment-after.json"
"${k[@]}" -n "$ns" rollout status "deployment/$deploy" --timeout=180s | tee "$out/rollout.txt"
"${k[@]}" -n "$ns" get pods -o json > "$out/pods-after.json"
echo "Rollout completed. Verify this Deployment's actual proxy images, istioctl proxy-status and application traffic before proceeding."
echo "This script does not establish traffic recovery. Keep evidence private; it can contain application configuration."
