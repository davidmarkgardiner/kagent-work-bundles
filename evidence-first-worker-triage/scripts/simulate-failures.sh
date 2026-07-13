#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == "--values" && -n "${2:-}" ]] || { echo "Usage: $0 --values /secure/pilot-values.env [--cleanup]" >&2; exit 2; }
VALUES="$2"; ACTION="${3:---apply}"
[[ "$ACTION" == "--apply" || "$ACTION" == "--cleanup" ]] || { echo "Use --apply or --cleanup" >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; source "$VALUES"; set +a
command -v envsubst >/dev/null || { echo "MISSING_DEPENDENCY: envsubst" >&2; exit 1; }
OUT="${OUT_DIR:-/tmp/evidence-first-worker-triage-rendered}/failure-fixtures.yaml"
mkdir -p "$(dirname "$OUT")"
envsubst '${PILOT_NAME} ${WORKER_NAMESPACE}' < "$ROOT/templates/failure-fixtures.yaml.tmpl" > "$OUT"
if [[ "$ACTION" == "--cleanup" ]]; then kubectl delete --ignore-not-found -f "$OUT"; echo "FIXTURES_CLEANED"; exit 0; fi
kubectl apply -f "$OUT"
echo "FAILURES_STARTED: log error, OOM, FailedScheduling and image pull fixtures"
echo "Then run: bash $ROOT/scripts/verify-healthy.sh --values $VALUES"
