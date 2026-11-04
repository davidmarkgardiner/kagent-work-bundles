#!/usr/bin/env bash
set -euo pipefail
umask 077
if [[ $# -lt 5 || $# -gt 6 ]]; then
  echo "Usage: $0 CONTEXT POLICY_NAMESPACE POLICY_NAME BAD_REV GOOD_REV [--apply]" >&2
  exit 2
fi
ctx=$1 ns=$2 policy=$3 bad=$4 good=$5 mode=${6:---plan}
[[ "$mode" == --plan || "$mode" == --apply ]] || exit 2
[[ -n "$ctx" && -n "$ns" && -n "$policy" && -n "$bad" && -n "$good" && "$bad" != "$good" ]] || exit 2
command -v jq >/dev/null
command -v kubectl >/dev/null
k=(kubectl --context "$ctx" --request-timeout=30s -n "$ns")
resource=peerauthentications.security.istio.io
out=$(mktemp -d "${TMPDIR:-/tmp}/peerauth-revision.XXXXXXXX")
echo "Private evidence directory: $out"
trap 'rc=$?; if [[ $rc -ne 0 ]]; then echo "STOPPED (exit $rc). Inspect $out. No automatic retry or undo." >&2; fi' EXIT
"${k[@]}" get "$resource" "$policy" -o json > "$out/before.json"
observed=$(jq -r '.metadata.labels["istio.io/rev"] // ""' "$out/before.json")
if [[ "$observed" == "$good" ]]; then
  echo "Label already equals $good. No write. Verify effective mTLS and application traffic."
  exit 0
fi
[[ "$observed" == "$bad" ]] || {
  echo "Unexpected revision '$observed'; expected '$bad'. No write." >&2; exit 1;
}
jq --arg bad "$bad" --arg good "$good" '[
  {op:"test",path:"/metadata/uid",value:.metadata.uid},
  {op:"test",path:"/metadata/resourceVersion",value:.metadata.resourceVersion},
  {op:"test",path:"/metadata/labels/istio.io~1rev",value:$bad},
  {op:"replace",path:"/metadata/labels/istio.io~1rev",value:$good}
]' "$out/before.json" > "$out/patch.json"
"${k[@]}" patch "$resource" "$policy" --type=json --patch-file "$out/patch.json" --dry-run=server -o json > "$out/dry-run.json"
jq -e --arg good "$good" --slurpfile before "$out/before.json" '
  .metadata.labels["istio.io/rev"] == $good
  and .metadata.uid == $before[0].metadata.uid
  and .spec == $before[0].spec
' "$out/dry-run.json" >/dev/null || {
  echo "Admission did not preserve the desired label and policy spec. No write." >&2; exit 1;
}
if [[ "$mode" != --apply ]]; then
  echo "PLAN ONLY: PeerAuthentication $ns/$policy revision $bad -> $good. Spec unchanged."
  echo "Before --apply: stop the offending Kyverno mutation and align the GitOps policy label."
  exit 0
fi
"${k[@]}" patch "$resource" "$policy" --type=json --patch-file "$out/patch.json" -o json > "$out/patch-response.json"
"${k[@]}" get "$resource" "$policy" -o json > "$out/after.json"
jq -e --arg good "$good" --slurpfile before "$out/before.json" '
  .metadata.labels["istio.io/rev"] == $good
  and .metadata.uid == $before[0].metadata.uid
  and .spec == $before[0].spec
' "$out/after.json" >/dev/null || {
  echo "POST-WRITE CHECK FAILED. A write occurred; inspect admission/GitOps/background mutation and saved evidence." >&2; exit 1;
}
echo "Stored PeerAuthentication revision is $good; spec unchanged."
echo "No namespace or workload was changed. Verify xDS, effective mTLS and real application traffic."
