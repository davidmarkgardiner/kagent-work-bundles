#!/usr/bin/env bash
set -euo pipefail
BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$BUNDLE_ROOT"
command -v python3 >/dev/null
command -v node >/dev/null
python3 -B scripts/audit_tools.py verify-checksums
python3 -B scripts/verify-upstream.py
python3 -B scripts/audit_tools.py verify-manifest
node --test upstream/security-audit/validate-findings.test.cjs upstream/security-audit/validate-coverage-ledger.test.cjs
python3 -B -m unittest discover -s tests -p 'test_*.py'
if command -v kubectl >/dev/null && [[ -f manifests/kustomization.yaml ]]; then
  kubectl kustomize manifests >/dev/null
else
  echo 'NOT ASSESSED: kubectl Kustomize rendering (optional tool or overlay unavailable)'
fi
echo 'PASS: offline bundle gates; no target audit, model invocation, or cluster proof'
