#!/usr/bin/env bash
# Stand up kagent with durable native memory (Postgres + pgvector) on an
# isolated kind cluster. Dev/eval only — uses the chart's BUNDLED Postgres with
# a pgvector image override. For work, use an external managed Postgres instead
# (see examples/values-pgvector.yaml).
#
# Proven 2026-07-16. Idempotent.
set -euo pipefail

CLUSTER="${CLUSTER:-kagent-memory}"
CTX="kind-${CLUSTER}"
NS="${NS:-kagent}"
KAGENT_VER="${KAGENT_VER:-0.9.10}"
PG_IMAGE_TAG="${PG_IMAGE_TAG:-pg17}"

for command in kind kubectl helm; do
  command -v "${command}" >/dev/null || {
    echo "FATAL required command not found: ${command}" >&2
    exit 2
  }
done

echo "== 1. kind cluster =="
kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --wait 90s

echo "== 2. kagent CRDs =="
helm upgrade --install kagent-crds oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  --version "$KAGENT_VER" -n "$NS" --create-namespace --kube-context "$CTX" --wait --timeout 5m

echo "== 3. kagent + bundled pgvector Postgres, vector migration on =="
helm upgrade --install kagent oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  --version "$KAGENT_VER" -n "$NS" --kube-context "$CTX" --wait --timeout 12m \
  --set registry=ghcr.io \
  --set database.postgres.vectorEnabled=true \
  --set database.postgres.bundled.enabled=true \
  --set database.postgres.bundled.image.registry=docker.io \
  --set database.postgres.bundled.image.repository=pgvector \
  --set database.postgres.bundled.image.name=pgvector \
  --set "database.postgres.bundled.image.tag=${PG_IMAGE_TAG}" \
  --set database.postgres.bundled.storage=1Gi

echo "== 4. verify backend =="
kubectl --context "$CTX" get cm -n "$NS" kagent-controller \
  -o jsonpath='DATABASE_VECTOR_ENABLED={.data.DATABASE_VECTOR_ENABLED}{"\n"}'
PGPOD=$(kubectl --context "$CTX" get pod -n "$NS" -l app.kubernetes.io/component=database -o name | head -1)
kubectl --context "$CTX" exec -n "$NS" "$PGPOD" -- \
  psql -U kagent -d kagent -tAc \
  "SELECT 'pgvector '||extversion FROM pg_extension WHERE extname='vector';"

echo "Done. Next: bash scripts/memory-durability-test.sh"
