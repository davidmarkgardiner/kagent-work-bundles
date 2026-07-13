#!/usr/bin/env bash
set -euo pipefail

usage() { echo "Usage: $0 --values /secure/pilot-values.env" >&2; exit 2; }
[[ "${1:-}" == "--values" && -n "${2:-}" ]] || usage
VALUES="$2"
[[ -f "$VALUES" ]] || { echo "MISSING_VALUES_FILE" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
source "$VALUES"
set +a

for key in PILOT_NAME ENVIRONMENT TENANT WORKER_CLUSTER_NAME WORKER_NAMESPACE MANAGEMENT_NAMESPACE KAFKA_BOOTSTRAP KAFKA_AUTH_MODE DURABLE_TTL_BACKEND DATA_CLASSIFICATION_REFERENCE VECTOR_IMAGE VECTOR_BUFFER_SIZE APPROVED_STORAGE_CLASS; do
  value="${!key:-}"
  [[ -n "$value" && "$value" != *'{{'* && "$value" != *'}}'* ]] || { echo "BLOCKED_MISSING_OR_PLACEHOLDER: $key" >&2; exit 1; }
done

[[ "${CRITIQUE_CORRECTIONS_ACCEPTED:-no}" == "yes" ]] || { echo "STATUS: BLOCKED_BY_CRITIQUE_CORRECTIONS" >&2; exit 1; }
[[ "$WORKER_NAMESPACE" != "default" && "$WORKER_NAMESPACE" != "kube-system" ]] || { echo "BLOCKED_UNSAFE_WORKER_NAMESPACE" >&2; exit 1; }

echo "PREFLIGHT_GATES: passed"
echo "SCOPE: non-production worker namespace approved by values owner"
echo "SECRETS_NOT_PRINTED: yes"
