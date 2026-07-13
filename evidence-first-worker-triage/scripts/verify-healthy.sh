#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == "--values" && -n "${2:-}" ]] || { echo "Usage: $0 --values /secure/pilot-values.env" >&2; exit 2; }
set -a; source "$2"; set +a
echo '== Worker Vector =='
kubectl -n "$WORKER_NAMESPACE" rollout status "deployment/$PILOT_NAME-vector" --timeout=180s
kubectl -n "$WORKER_NAMESPACE" get pods,svc,pvc -l "app.kubernetes.io/name=$PILOT_NAME-vector"
echo '== Management Argo =='
kubectl -n "$MANAGEMENT_NAMESPACE" get eventsource,sensor,workflowtemplate "$PILOT_NAME-confluent" "$PILOT_NAME-triage" "$PILOT_NAME-triage"
kubectl -n "$MANAGEMENT_NAMESPACE" get pods -l eventsource-name="$PILOT_NAME-confluent"
echo '== Recent triage workflows =='
kubectl -n "$MANAGEMENT_NAMESPACE" get workflows --sort-by=.metadata.creationTimestamp | tail -10
echo '== Required existing secrets (names only) =='
kubectl -n "$WORKER_NAMESPACE" get secret "$KAFKA_SECRET_NAME"
kubectl -n "$MANAGEMENT_NAMESPACE" get secret "$KAFKA_SECRET_NAME" "$KAFKA_CA_SECRET_NAME" "$IDEMPOTENCY_SECRET_NAME" "$GITLAB_SECRET_NAME"
echo 'HEALTH_CHECK_COMPLETE: inspect EventSource/Sensor conditions and Vector logs if any check is not Ready.'
