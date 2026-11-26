# Sourced by the other scripts.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$HERE/versions.env"
: "${KUBE_CONTEXT:?source env.sh first}" "${REGISTRY:?set REGISTRY}"
k() { kubectl --context "$KUBE_CONTEXT" "$@"; }
# POST_RENDERER: optional Helm 3 post-renderer (path to an executable), for admission policy.
h() { helm --kube-context "$KUBE_CONTEXT" "$@" ${POST_RENDERER:+--post-renderer "$POST_RENDERER"}; }
say() { printf '\n==> %s\n' "$*"; }
