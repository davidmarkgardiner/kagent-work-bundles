#!/usr/bin/env bash
# Mirror Istio 1.31.4 charts and images into your own registry. DRY RUN by default: it prints the commands.
#   REGISTRY=myacr.azurecr.io NEEDS=sidecar,cni ./mirror.sh            # print the plan
#   REGISTRY=myacr.azurecr.io NEEDS=sidecar,cni ./mirror.sh --apply    # do it
# NEEDS: any of sidecar, cni, ingress, ambient, grpc, distroless (see images.txt / charts.txt). Default: sidecar,cni.
# Images go to <REGISTRY>/<target> (e.g. myacr.azurecr.io/istio/pilot:1.31.4); charts to oci://<REGISTRY>/<CHART_PATH>.
# Image copy tool, first found: az (ACR import, server-side, keeps all architectures), crane, skopeo, then docker (amd64 only).
# Run it where Docker Hub and blob.istio.io are reachable and you are logged in to the target registry
# (az acr login --name <acr>, or helm registry login / docker login). Charts are verified against charts.txt first.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REGISTRY="${REGISTRY:?set REGISTRY, e.g. myacr.azurecr.io}"
NEEDS=",${NEEDS:-sidecar,cni},"
CHART_PATH="${CHART_PATH:-helm/istio}"
CHART_REPO="${CHART_REPO:-https://blob.istio.io/istio-release/charts}"
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
run() { if [ "$APPLY" = 1 ]; then echo "+ $*"; "$@"; else echo "  $*"; fi; }
want() { case "$NEEDS" in *",$1,"*) return 0;; esac; return 1; }
TOOL="${TOOL:-}"
if [ -z "$TOOL" ]; then
  if command -v az >/dev/null && [[ "$REGISTRY" == *.azurecr.io* ]]; then TOOL=az
  elif command -v crane >/dev/null; then TOOL=crane
  elif command -v skopeo >/dev/null; then TOOL=skopeo
  else TOOL=docker; fi
fi
[ "$APPLY" = 1 ] || echo "DRY RUN (pass --apply to execute). Registry: $REGISTRY  needs: ${NEEDS//,/ }  image tool: $TOOL"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
echo "== charts -> oci://$REGISTRY/$CHART_PATH"
grep -vE '^\s*(#|$)' "$HERE/charts.txt" | while read -r need name ver sum; do
  want "$need" || continue
  if [ "$APPLY" = 1 ]; then
    helm pull "$name" --repo "$CHART_REPO" --version "$ver" -d "$WORK" >/dev/null
    got="$(shasum -a 256 "$WORK/$name-$ver.tgz" 2>/dev/null || sha256sum "$WORK/$name-$ver.tgz")"; got="${got%% *}"
    [ "$got" = "$sum" ] || { echo "checksum mismatch for $name-$ver.tgz: $got (want $sum)" >&2; exit 1; }
  else echo "  helm pull $name --repo $CHART_REPO --version $ver   # verify sha256 $sum"; fi
  run helm push "$WORK/$name-$ver.tgz" "oci://$REGISTRY/$CHART_PATH"
done

echo "== images -> $REGISTRY"
grep -vE '^\s*(#|$)' "$HERE/images.txt" | while read -r need src target; do
  want "$need" || continue
  repo_digest="${src%@*}"; digest="${src#*@}"; plain="${repo_digest%:*}@$digest"
  case "$TOOL" in
    az)     run az acr import --name "${REGISTRY%%.*}" --source "$plain" --image "$target" --force ;;
    crane)  run crane copy "$plain" "$REGISTRY/$target" ;;
    skopeo) run skopeo copy --all "docker://$plain" "docker://$REGISTRY/$target" ;;
    docker) run docker pull --platform linux/amd64 "$plain"; run docker tag "$plain" "$REGISTRY/$target"; run docker push "$REGISTRY/$target" ;;
  esac
done
echo "Done. Install with values-airgap.yaml (set global.hub to $REGISTRY/istio). See README.md."
