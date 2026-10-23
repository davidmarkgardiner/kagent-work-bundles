#!/usr/bin/env bash
# Validate edited manifests independently of the original delivery checksums.
set -euo pipefail
BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for bin in python3 kubectl; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required tool: $bin" >&2; exit 1; }
done
python3 "$BUNDLE_ROOT/scripts/validate-agent-cr.py" "$BUNDLE_ROOT/manifests/agent.yaml" --type triage
RENDERED="$(mktemp)"
trap 'rm -f "$RENDERED"' EXIT
kubectl kustomize "$BUNDLE_ROOT/manifests" > "$RENDERED"
python3 "$BUNDLE_ROOT/scripts/validate-security-profile.py" "$BUNDLE_ROOT/manifests/agent.yaml" "$RENDERED"
