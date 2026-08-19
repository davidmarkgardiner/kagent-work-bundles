#!/usr/bin/env sh
set -eu

root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
repo="$(CDPATH='' cd -- "$root/../.." && pwd)"

command -v rg >/dev/null
command -v python3 >/dev/null
command -v kubectl >/dev/null

if rg -n -i \
  'MCPG_DATABASE_URL|POSTGRES_PASSWORD|PGPASSWORD|postgres-url|secretKeyRef|kind:[[:space:]]*Secret' \
  "$root/adapter" \
  --glob '*.yaml' --glob '*.yml' --glob '*.py' --glob 'Dockerfile' \
  --glob 'requirements.txt' --glob '*.sql' --glob '*.template' --glob '*.sh'; then
  echo "FASTMCP_UAMI_BUNDLE_BOUNDARY_FAILED" >&2
  exit 1
fi

python3 -c 'from pathlib import Path; [compile(p.read_text(), str(p), "exec") for p in (Path("'"$root"'") / "adapter").glob("*.py")]'
sh -n "$root/adapter/verify-live.sh"
if command -v shellcheck >/dev/null; then
  shellcheck "$root/adapter/verify-live.sh"
fi

# Kustomize requires the ignored workplace values file. When it is not present,
# use the public placeholder template only to validate replacement structure.
created_values=false
if [ ! -f "$root/work-values.env" ]; then
  cp "$root/work-values.env.template" "$root/work-values.env"
  created_values=true
fi
cleanup_values() {
  if [ "$created_values" = true ]; then
    unlink "$root/work-values.env"
  fi
}
trap cleanup_values EXIT HUP INT TERM
kubectl kustomize "$root" >/dev/null

"$repo/scripts/public-safe-scan.sh" "$root"
echo "FASTMCP_UAMI_BUNDLE_VERIFY_OK"
