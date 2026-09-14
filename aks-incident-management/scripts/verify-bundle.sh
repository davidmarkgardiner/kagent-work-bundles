#!/bin/sh
set -eu

bundle_dir=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
status=0

npm --prefix "$bundle_dir/image" ci --ignore-scripts || status=1
npm --prefix "$bundle_dir/image" test || status=1

if command -v docker >/dev/null 2>&1; then
  docker build --check "$bundle_dir/image" || status=1
else
  echo "SKIP docker build check: docker not installed"
fi

if find "$bundle_dir" -path '*/node_modules' -prune -o -type f ! -path '*/rendered/*' ! -path "$bundle_dir/scripts/verify-bundle.sh" -print0 | xargs -0 grep -n -E '(glpat-|Bearer [A-Za-z0-9_-]{20,}|password:[[:space:]]+[^{$])'; then
  echo "possible literal credential found" >&2
  status=1
fi

if [ -d "$bundle_dir/rendered" ]; then
  if command -v ruby >/dev/null 2>&1; then
    ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_stream(File.read(f)) }' "$bundle_dir"/rendered/*.yaml || status=1
  fi
  if command -v kubectl >/dev/null 2>&1 && kubectl config current-context >/dev/null 2>&1; then
    kubectl create --dry-run=client -f "$bundle_dir/rendered" >/dev/null || status=1
  else
    echo "SKIP Kubernetes client dry-run: no current context"
  fi
else
  echo "SKIP rendered manifest validation: run scripts/render.sh first"
fi

if [ -x "$bundle_dir/../../scripts/public-safe-scan.sh" ]; then
  "$bundle_dir/../../scripts/public-safe-scan.sh" "$bundle_dir" --allowlist "$bundle_dir/.public-safe-allowlist" || status=1
fi

exit "$status"
