#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 --values /secure/pilot-values.env --out /tmp/rendered-pilot" >&2; exit 2; }
[[ "${1:-}" == "--values" && -n "${2:-}" && "${3:-}" == "--out" && -n "${4:-}" ]] || usage
VALUES="$2"
OUT="$4"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT/scripts/preflight-gates.sh" --values "$VALUES"
command -v envsubst >/dev/null || { echo "MISSING_DEPENDENCY: envsubst" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$VALUES"
set +a
mkdir -p "$OUT"

VARS='${PILOT_NAME} ${ENVIRONMENT} ${TENANT} ${WORKER_CLUSTER_NAME} ${WORKER_NAMESPACE} ${MANAGEMENT_NAMESPACE} ${KAFKA_AUTH_MODE} ${DURABLE_TTL_BACKEND} ${DATA_CLASSIFICATION_REFERENCE} ${VECTOR_IMAGE} ${VECTOR_BUFFER_SIZE} ${APPROVED_STORAGE_CLASS}'
for template in "$ROOT"/templates/*.tmpl; do
  target="$OUT/$(basename "${template%.tmpl}")"
  envsubst "$VARS" < "$template" > "$target"
  [[ ! -s "$target" ]] && { echo "EMPTY_RENDER: $target" >&2; exit 1; }
  echo "RENDERED $(basename "$target")"
done

echo "RENDER_DIR: $OUT"
echo "APPLY_PERFORMED: no"
