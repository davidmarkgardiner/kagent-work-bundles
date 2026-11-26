# Sourced by the other scripts.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$HERE/versions.env"
: "${KUBE_CONTEXT:?source env.sh first}" "${REGISTRY:?set REGISTRY}"
k() { kubectl --context "$KUBE_CONTEXT" "$@"; }
h() { helm --kube-context "$KUBE_CONTEXT" "$@"; }
say() { printf '\n==> %s\n' "$*"; }
