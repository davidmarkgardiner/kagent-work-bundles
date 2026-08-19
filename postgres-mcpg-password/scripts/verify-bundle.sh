#!/usr/bin/env sh
set -eu

root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
repo="$(CDPATH='' cd -- "$root/../.." && pwd)"

command -v rg >/dev/null
command -v kubectl >/dev/null

if rg -n -i \
  'from fastmcp|azure[._-]identity|azure-postgresql-auth|azure\.workload\.identity|pgaadauth_create|UAMI_CLIENT_ID|UAMI_OBJECT_ID' \
  "$root" \
  --glob '*.yaml' --glob '*.yml' --glob '*.py' --glob 'Dockerfile' \
  --glob '*.sql' --glob '*.template'; then
  echo "MCPG_PASSWORD_BUNDLE_BOUNDARY_FAILED" >&2
  exit 1
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
echo "MCPG_PASSWORD_BUNDLE_VERIFY_OK"
