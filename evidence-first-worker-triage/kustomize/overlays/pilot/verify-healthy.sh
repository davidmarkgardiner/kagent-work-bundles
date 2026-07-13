#!/usr/bin/env bash
set -euo pipefail
VALUES="${1:-values.env}"
[[ -f "$VALUES" ]] || { echo "Usage: $0 [values.env]" >&2; exit 2; }
set -a; source "$VALUES"; set +a
echo '== Demo collector and local processing =='
kubectl -n "$WORKER_NAMESPACE" rollout status deployment/evidence-first-alloy --timeout=180s
kubectl -n "$WORKER_NAMESPACE" rollout status deployment/evidence-first-vector --timeout=180s
kubectl -n "$WORKER_NAMESPACE" get pods,svc,pvc,pdb
echo '== Management consumer and orchestration =='
kubectl -n "$MANAGEMENT_NAMESPACE" get eventsource evidence-first-confluent
kubectl -n "$MANAGEMENT_NAMESPACE" get sensor evidence-first-triage
kubectl -n "$MANAGEMENT_NAMESPACE" get workflowtemplate evidence-first-triage
echo '== EventSource consumer status =='
kubectl -n "$MANAGEMENT_NAMESPACE" get pods -l eventsource-name=evidence-first-confluent
kubectl -n "$MANAGEMENT_NAMESPACE" logs -l eventsource-name=evidence-first-confluent --tail=30 || true
echo '== Recent workflows =='
kubectl -n "$MANAGEMENT_NAMESPACE" get workflows --sort-by=.metadata.creationTimestamp | tail -10
echo 'HEALTHY means both worker Deployments are Available and EventSource/Sensor pods are Running; inspect the consumer logs for Kafka connection errors.'
