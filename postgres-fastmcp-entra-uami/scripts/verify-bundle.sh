#!/usr/bin/env sh
set -eu

root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
repo="$(CDPATH='' cd -- "$root/../.." && pwd)"

command -v rg >/dev/null
command -v python3 >/dev/null
command -v kubectl >/dev/null

if rg -n -i 'MCPG_DATABASE_URL|PGPASSWORD|postgres-url' \
  "$root/adapter/server.py" "$root/adapter/verify_live.py" \
  "$root/adapter/aks-workload-identity.yaml.template" \
  "$root/password/fastmcp-password.yaml.template"; then
  echo "FASTMCP_DUAL_AUTH_BOUNDARY_FAILED" >&2
  exit 1
fi

if rg -n -i 'POSTGRES_PASSWORD|secretKeyRef' \
  "$root/adapter/aks-workload-identity.yaml.template"; then
  echo "FASTMCP_UAMI_MANIFEST_CONTAINS_PASSWORD_PATH" >&2
  exit 1
fi

if rg -n -i 'azure\.workload\.identity|UAMI_CLIENT_ID|DefaultAzureCredential' \
  "$root/password" --glob '*.yaml' --glob '*.template'; then
  echo "FASTMCP_PASSWORD_MANIFEST_CONTAINS_UAMI_PATH" >&2
  exit 1
fi

python3 -c 'from pathlib import Path; [compile(p.read_text(), str(p), "exec") for p in (Path("'"$root"'") / "adapter").glob("*.py")]'
(cd "$root/adapter" && python3 -m unittest -v test_result_budget.py)
if rg -n 'fetchall\(' "$root/adapter/server.py"; then
  echo "FASTMCP_UNBOUNDED_FETCH_FAILED" >&2
  exit 1
fi
rg -q 'fetchmany\(RESULT_BUDGET\.max_rows \+ 1\)' "$root/adapter/server.py"
sh -n "$root/adapter/verify-live.sh"
if command -v shellcheck >/dev/null; then
  shellcheck "$root/adapter/verify-live.sh"
fi

python3 - "$root/token-efficient-query-skill/postgres-token-efficient-query/references/sql-policy-cases.json" <<'PY'
import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text())
cases = {case["id"]: case for case in data["cases"]}
required = {
    "allow-count-star": "allow",
    "allow-filtered-group": "allow",
    "deny-projection-star": "deny",
    "deny-qualified-star": "deny",
    "deny-unbounded-detail": "deny",
    "deny-unapproved-source": "deny",
    "deny-write-cte": "deny",
    "deny-multiple-statements": "deny",
}
if {name: cases[name]["decision"] for name in required} != required:
    raise SystemExit("SQL policy cases do not match the required decisions")
if "count(*)" not in cases["allow-count-star"]["sql"].lower():
    raise SystemExit("COUNT(*) allow case is missing")
if "select *" not in cases["deny-projection-star"]["sql"].lower():
    raise SystemExit("projection wildcard deny case is missing")
print("POSTGRES_TOKEN_EFFICIENT_SQL_POLICY_CASES_OK")
PY

skill_root="$root/token-efficient-query-skill/postgres-token-efficient-query"
rg -q '^name: postgres-token-efficient-query$' "$skill_root/SKILL.md"
rg -q 'Treat `truncated: true` as a stopping condition' "$skill_root/SKILL.md"
rg -q 'COPY postgres-token-efficient-query/ /' \
  "$root/token-efficient-query-skill/Dockerfile"
echo "POSTGRES_TOKEN_EFFICIENT_SKILL_PACKAGE_OK"

template_root="$root/token-efficient-query-skill-template/postgres-domain-query-template"
rg -q '^name: postgres-domain-query-template$' "$template_root/SKILL.md"
rg -q 'Do not install this unfilled template' "$template_root/SKILL.md"
for reference in data-contract.md tool-routing.md verified-question-patterns.md evaluation-cases.md; do
  test -f "$template_root/references/$reference"
done
rg -Fq 'COPY postgres-domain-query-template/' \
  "$root/token-efficient-query-skill-template/Dockerfile.template"
rg -Fq '{{DOMAIN_NAME}}' "$template_root/references/data-contract.md"
rg -q 'cumulative session tokens' "$template_root/references/evaluation-cases.md"
echo "POSTGRES_DOMAIN_QUERY_SKILL_TEMPLATE_OK"

# Kustomize requires the ignored workplace values file. When it is not present,
# use the public placeholder template only to validate replacement structure.
created_values=false
if [ ! -f "$root/work-values.env" ]; then
  cp "$root/work-values.env.template" "$root/work-values.env"
  created_values=true
fi
cleanup_values() {
  if [ "$created_values" = true ]; then
    unlink "$root/work-values.env"
  fi
}
trap cleanup_values EXIT HUP INT TERM
uami_render="$(mktemp)"
kubectl kustomize "$root" >"$uami_render"

created_password_values=false
if [ ! -f "$root/password/work-values.env" ]; then
  cp "$root/password/work-values.env.template" "$root/password/work-values.env"
  created_password_values=true
fi
cleanup_password_values() {
  if [ "$created_password_values" = true ]; then
    unlink "$root/password/work-values.env"
  fi
}
trap 'cleanup_password_values; cleanup_values' EXIT HUP INT TERM
password_render="$(mktemp)"
kubectl kustomize "$root/password" >"$password_render"

rg -q 'value: entra' "$uami_render"
if rg -q 'name: POSTGRES_(USER|PASSWORD)|secretKeyRef:' "$uami_render"; then
  echo "FASTMCP_UAMI_RENDER_CONTAINS_PASSWORD_WIRING" >&2
  exit 1
fi

rg -q 'value: password' "$password_render"
test "$(rg -c 'secretKeyRef:' "$password_render")" -eq 2
if rg -q 'azure\.workload\.identity|UAMI_CLIENT_ID' "$password_render"; then
  echo "FASTMCP_PASSWORD_RENDER_CONTAINS_UAMI_WIRING" >&2
  exit 1
fi

for tool in get_inventory_data_product_details get_namespace_count get_namespace_summary; do
  test "$(rg -c -- "- $tool" "$uami_render")" -eq 1
  test "$(rg -c -- "- $tool" "$password_render")" -eq 1
done

unlink "$uami_render"
unlink "$password_render"

"$repo/scripts/public-safe-scan.sh" "$root"
echo "FASTMCP_DUAL_AUTH_BUNDLE_VERIFY_OK"
