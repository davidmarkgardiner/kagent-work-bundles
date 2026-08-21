#!/usr/bin/env bash
# Render and validate one Kubernetes YAML file or Kustomize directory without mutation.
set -euo pipefail

PATH_TO_VALIDATE=""
CONTEXT=""
SERVER_DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/validate-manifests.sh --path FILE_OR_KUSTOMIZE_DIR [options]

Options:
  --path PATH          A YAML file or Kustomize directory (required)
  --server-dry-run     Opt in to Kubernetes API validation; never mutates resources
  --context CONTEXT    Required together with --server-dry-run
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) PATH_TO_VALIDATE="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --server-dry-run) SERVER_DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$PATH_TO_VALIDATE" ]] || { echo "BLOCKED --path is required" >&2; exit 2; }
[[ -e "$PATH_TO_VALIDATE" ]] || { echo "BLOCKED path does not exist: $PATH_TO_VALIDATE" >&2; exit 2; }
if [[ "$SERVER_DRY_RUN" -eq 1 && -z "$CONTEXT" ]]; then
  echo "BLOCKED --server-dry-run requires an explicit --context" >&2
  exit 2
fi

for bin in kubectl python3; do
  command -v "$bin" >/dev/null || { echo "BLOCKED required binary missing: $bin" >&2; exit 2; }
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RENDERED="$(mktemp "${TMPDIR:-/tmp}/kubernetes-delivery-rendered.XXXXXX.yaml")"
trap 'rm -f "$RENDERED"' EXIT

if [[ -d "$PATH_TO_VALIDATE" ]]; then
  echo "STEP render kustomize: $PATH_TO_VALIDATE"
  kubectl kustomize "$PATH_TO_VALIDATE" > "$RENDERED"
else
  echo "STEP load manifest: $PATH_TO_VALIDATE"
  cp "$PATH_TO_VALIDATE" "$RENDERED"
fi

test -s "$RENDERED" || { echo "FAIL rendered output is empty" >&2; exit 1; }
echo "STEP client-side Kubernetes dry-run"
kubectl apply --dry-run=client --validate=true -f "$RENDERED" >/dev/null
echo "STEP deterministic manifest policy"
python3 "$ROOT/scripts/check_manifest_policy.py" "$RENDERED"

if [[ "$SERVER_DRY_RUN" -eq 1 ]]; then
  echo "STEP server-side Kubernetes dry-run on explicit context: $CONTEXT"
  kubectl --context "$CONTEXT" apply --dry-run=server --validate=true -f "$RENDERED" >/dev/null
fi

echo "PASS manifest validation completed (server-dry-run=$SERVER_DRY_RUN)"
