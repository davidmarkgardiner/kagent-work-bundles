#!/usr/bin/env sh
set -eu

context="${1:-}"
case "$context" in
  kind-*) ;;
  *) echo "usage: $0 kind-CLUSTER_NAME" >&2; exit 2 ;;
esac

root="$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)"
namespace="fastmcp-budget-test"
image="fastmcp-postgres-budget:local"
skill_image="postgres-token-efficient-query-skill:local"
cluster_name="${context#kind-}"
tmp_dir="$(mktemp -d)"
created_namespace=false
skill_container=""
running_nodes=""

cleanup() {
  if [ "$created_namespace" = true ] && [ "${KEEP_LOCAL_K8S_TEST:-false}" != true ]; then
    kubectl --context "$context" delete namespace "$namespace" --wait=false >/dev/null 2>&1 || true
  fi
  if [ -n "$skill_container" ]; then
    docker rm -f "$skill_container" >/dev/null 2>&1 || true
  fi
  for node in $running_nodes; do
    docker exec "$node" ctr --namespace k8s.io images remove \
      docker.io/library/fastmcp-postgres-budget:local >/dev/null 2>&1 || true
  done
  docker image rm "$image" "$skill_image" >/dev/null 2>&1 || true
  rm -f "$tmp_dir/tls.crt" "$tmp_dir/tls.key"
  rmdir "$tmp_dir" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

for command_name in docker kind kubectl openssl; do
  command -v "$command_name" >/dev/null
done
docker info >/dev/null
kubectl --context "$context" get --raw=/readyz >/dev/null

if kubectl --context "$context" get namespace "$namespace" >/dev/null 2>&1; then
  echo "refusing to reuse existing namespace: $namespace" >&2
  exit 1
fi

docker build --tag "$image" "$root/adapter"
docker build --tag "$skill_image" "$root/token-efficient-query-skill"
skill_container="$(docker create "$skill_image" /bin/true)"
skill_contents="$(docker export "$skill_container" | tar -tf -)"
printf '%s\n' "$skill_contents" | grep -qx 'SKILL.md'
printf '%s\n' "$skill_contents" | grep -qx 'references/legacy-sql-policy.md'
printf '%s\n' "$skill_contents" | grep -qx 'references/sql-policy-cases.json'
docker rm "$skill_container" >/dev/null
skill_container=""
echo "POSTGRES_TOKEN_EFFICIENT_SKILL_IMAGE_OK"
running_nodes="$(docker ps \
  --filter "label=io.x-k8s.kind.cluster=$cluster_name" \
  --format '{{.Names}}')"
if [ -z "$running_nodes" ]; then
  echo "no running nodes found for kind cluster: $cluster_name" >&2
  exit 1
fi
for node in $running_nodes; do
  docker save "$image" | docker exec -i "$node" \
    ctr --namespace k8s.io images import - >/dev/null
done

kubectl --context "$context" create namespace "$namespace" >/dev/null
created_namespace=true

admin_credential="$(openssl rand -hex 24)"
reader_credential="$(openssl rand -hex 24)"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj '/CN=postgres-budget' \
  -addext 'subjectAltName=DNS:postgres-budget,DNS:postgres-budget.fastmcp-budget-test.svc' \
  -keyout "$tmp_dir/tls.key" -out "$tmp_dir/tls.crt" >/dev/null 2>&1

kubectl --context "$context" --namespace "$namespace" create secret generic \
  postgres-budget-credentials \
  --from-literal=admin-credential="$admin_credential" \
  --from-literal=reader-credential="$reader_credential" >/dev/null
kubectl --context "$context" --namespace "$namespace" create secret tls \
  postgres-budget-tls --cert="$tmp_dir/tls.crt" --key="$tmp_dir/tls.key" >/dev/null
unset admin_credential reader_credential

kubectl --context "$context" --namespace "$namespace" apply \
  -f "$root/tests/local-k8s/resources.yaml" >/dev/null
kubectl --context "$context" --namespace "$namespace" rollout status \
  deployment/postgres-budget --timeout=180s
kubectl --context "$context" --namespace "$namespace" rollout status \
  deployment/fastmcp-budget --timeout=180s

# The quoted command is expanded inside the PostgreSQL container.
# shellcheck disable=SC2016
seeded_rows="$(kubectl --context "$context" --namespace "$namespace" exec \
  deployment/postgres-budget -- sh -ec \
  'PGPASSWORD="$POSTGRES_PASSWORD" psql -At -U postgres -d budget_test -c "SELECT count(*) FROM work_inventory.approved_namespaces"')"
test "$seeded_rows" = 5000
echo "POSTGRES_BUDGET_FIXTURE_5000_ROWS_OK"

kubectl --context "$context" --namespace "$namespace" exec \
  deployment/fastmcp-budget -- python /app/verify_budget_live.py
kubectl --context "$context" --namespace "$namespace" exec \
  deployment/fastmcp-budget -- python /app/verify_mcp_transport.py
