#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BUNDLE_ROOT"

for bin in python3 kubectl; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required tool: $bin" >&2; exit 1; }
done
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum --check CHECKSUMS.sha256
else
  shasum -a 256 --check CHECKSUMS.sha256
fi

bash scripts/validate-manifests.sh

echo 'PASS offline work bundle; target deployment and scan remain unverified'
