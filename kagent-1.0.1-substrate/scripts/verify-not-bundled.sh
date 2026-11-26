#!/usr/bin/env bash
# Read-only. Pulls the locked charts and checks that the kagent chart does not
# contain or install Substrate. Never contacts a Kubernetes cluster.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
SRC="${SOURCE_REGISTRY:-}"   # set to a mirror host to pull from it instead of ghcr.io
fail=0
check() { if [ "$1" = 0 ]; then echo "PASS  $2"; else echo "FAIL  $2"; fail=1; fi; }

while read -r name version repo digest; do
  case "$name" in ''|\#*) continue ;; esac
  [ -n "$SRC" ] && repo="$SRC/${repo#*/}"
  out="$(helm pull "oci://$repo/$name" --version "$version" -d "$WORK" 2>&1)" || { echo "$out"; exit 1; }
  grep -q "$digest" <<<"$out"; check $? "digest $name $version"
done < "$HERE/charts.lock"

chart="$WORK/kagent-1.0.1.tgz"
deps="$(helm show chart "$chart" | awk '/^dependencies:/{f=1;next} /^[a-z]/{f=0} f && /name:/{print $NF}' | sort | tr '\n' ' ')"
echo "      kagent chart dependencies: $deps"
[ "$deps" = "kagent-tools oauth2-proxy " ]; check $? "kagent chart has no substrate dependency"

tar -xzf "$chart" -C "$WORK"
[ -z "$(find "$WORK/kagent/charts" -maxdepth 1 -iname '*substrate*')" ]; check $? "no substrate subchart packaged"

helm template kagent "$chart" -n kagent --set providers.openAI.apiKey=x \
  --set substrateWorkerPool.create=true --set substrateWorkerPool.workerImage=example.invalid/worker:x \
  > "$WORK/kagent.yaml"
! grep -qE 'image: .*(ateapi|atelet|atecontroller|atenet|ate-idp-server|podcertcontroller|rustfs)' "$WORK/kagent.yaml"
check $? "kagent render contains no Substrate control-plane images"
grep -q '^kind: WorkerPool' "$WORK/kagent.yaml"
check $? "kagent render does consume Substrate (creates a WorkerPool, CRD must already exist)"

echo
[ "$fail" = 0 ] && echo "RESULT: Substrate is NOT bundled in the kagent chart. Install it separately." \
               || echo "RESULT: at least one check failed. Stop and report."
exit "$fail"
