#!/usr/bin/env bash
set -euo pipefail
usage() { echo "Usage: $0 --values /secure/pilot-values.env [--apply]" >&2; exit 2; }
[[ "${1:-}" == "--values" && -n "${2:-}" ]] || usage
VALUES="$2"; MODE="${3:---dry-run}"
[[ "$MODE" == "--dry-run" || "$MODE" == "--apply" ]] || usage
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/preflight-gates.sh" --values "$VALUES"
command -v envsubst >/dev/null || { echo "MISSING_DEPENDENCY: envsubst" >&2; exit 1; }
set -a; source "$VALUES"; set +a
OUT="${OUT_DIR:-/tmp/evidence-first-worker-triage-rendered}"
rm -rf "$OUT"; mkdir -p "$OUT"
VARS='${PILOT_NAME} ${ENVIRONMENT} ${TENANT} ${WORKER_CLUSTER_NAME} ${WORKER_NAMESPACE} ${MANAGEMENT_NAMESPACE} ${KAFKA_BOOTSTRAP} ${KAFKA_TOPIC} ${KAFKA_CONSUMER_GROUP} ${KAFKA_SECRET_NAME} ${KAFKA_USERNAME_KEY} ${KAFKA_PASSWORD_KEY} ${KAFKA_CA_SECRET_NAME} ${KAFKA_CA_SECRET_KEY} ${VECTOR_IMAGE} ${VECTOR_BUFFER_SIZE} ${APPROVED_STORAGE_CLASS} ${WORKER_VECTOR_SERVICE_ACCOUNT} ${ARGO_EVENTS_SERVICE_ACCOUNT} ${ARGO_WORKFLOW_SERVICE_ACCOUNT} ${IDEMPOTENCY_CLAIM_URL} ${IDEMPOTENCY_SECRET_NAME} ${IDEMPOTENCY_TOKEN_KEY} ${KAGENT_A2A_URL} ${KAGENT_AGENT_NAME} ${GITLAB_SECRET_NAME} ${GITLAB_URL_KEY} ${GITLAB_TOKEN_KEY} ${GITLAB_PROJECT_ID_KEY}'
for name in worker-evidence-pilot management-triage-pilot; do envsubst "$VARS" < "$ROOT/templates/$name.yaml.tmpl" > "$OUT/$name.yaml"; done
kubectl apply --dry-run=server -f "$OUT/worker-evidence-pilot.yaml"
kubectl apply --dry-run=server -f "$OUT/management-triage-pilot.yaml"
if [[ "$MODE" == "--apply" ]]; then
  kubectl apply -f "$OUT/worker-evidence-pilot.yaml"
  kubectl apply -f "$OUT/management-triage-pilot.yaml"
  echo "APPLIED: $OUT"
else
  echo "DRY_RUN_PASSED: $OUT"
fi
