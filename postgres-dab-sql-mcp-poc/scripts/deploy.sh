#!/usr/bin/env sh
set -eu

context=red
[ "$#" -gt 0 ] && context="$1"
root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
require() { command -v "$1" >/dev/null || { echo "MISSING_COMMAND $1" >&2; exit 2; }; }
require kubectl
require base64

namespace=postgres-dab-mcp-poc
kubectl --context "$context" create namespace "$namespace" --dry-run=client -o yaml | kubectl --context "$context" apply -f -
# This public bundle deliberately requires pre-created lab Secret objects. It
# never generates, reads, or prints credentials. Create the two Secret objects
# through the environment's approved secret-delivery mechanism, with keys:
# postgres-dab-poc-admin/credential and postgres-dab-poc-reader/{credential,
# connection-string,postgres-url}. Work must use short-lived identity/secret
# delivery rather than copying these lab names verbatim.
for secret_name in postgres-dab-poc-admin postgres-dab-poc-reader; do
  kubectl --context "$context" -n "$namespace" get secret "$secret_name" >/dev/null \
    || { echo "MISSING_PREREQUISITE_SECRET $secret_name" >&2; exit 2; }
done
kubectl --context "$context" apply -f "$root/postgres.yaml"
kubectl --context "$context" -n "$namespace" rollout status deployment/postgres-dab-poc --timeout=3m
kubectl --context "$context" -n "$namespace" delete job/postgres-dab-poc-seed --ignore-not-found
kubectl --context "$context" apply -f "$root/seed-job.yaml"
kubectl --context "$context" -n "$namespace" wait --for=condition=complete job/postgres-dab-poc-seed --timeout=3m
if [ "${WITH_DAB_EXPERIMENT:-false}" = true ]; then
  kubectl --context "$context" apply -f "$root/dab.yaml"
  # DAB reads the mounted configuration on process start; restart after a
  # ConfigMap change so the optional experiment validates checked-in config.
  kubectl --context "$context" -n "$namespace" rollout restart deployment/postgres-dab-sql-mcp
  kubectl --context "$context" -n "$namespace" rollout status deployment/postgres-dab-sql-mcp --timeout=3m
  kubectl --context "$context" apply -f "$root/kagent-agent.yaml"
fi
kubectl --context "$context" apply -f "$root/postgres-adapter.yaml"
kubectl --context "$context" -n "$namespace" rollout restart deployment/postgres-compliance-mcp
kubectl --context "$context" -n "$namespace" rollout status deployment/postgres-compliance-mcp --timeout=4m
kubectl --context "$context" apply -f "$root/kagent-postgres-adapter-agent.yaml"
# A RemoteMCPServer can briefly be NotAccepted while its backend restarts.
# Do not hand the bundle to verification until the controller has rediscovered
# the bounded tool surface.
kubectl --context "$context" -n kagent wait --for=condition=Accepted remotemcpserver/postgres-kubernetes-inventory-readonly-mcp --timeout=3m
kubectl --context "$context" -n kagent wait --for=condition=Ready agent/postgres-kubernetes-inventory-lab-agent --timeout=3m
