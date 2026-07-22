#!/usr/bin/env bash
# Read-only verifier: confirms the durable-memory backend is wired correctly on
# ANY cluster (kind lab or work AKS). Mutates nothing. Pass --context for AKS.
set -euo pipefail
CTX="${1:-kind-kagent-memory}"; [ "$CTX" = "--context" ] && CTX="$2"
NS="${NS:-kagent}"
FAILURES=0
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }
command -v kubectl >/dev/null || { echo "ERROR kubectl is required" >&2; exit 2; }
echo "== context: $CTX  namespace: $NS =="

echo "-- DATABASE_VECTOR_ENABLED (expect true) --"
VECTOR_ENABLED=$(kubectl --context "$CTX" get cm -n "$NS" kagent-controller \
  -o jsonpath='{.data.DATABASE_VECTOR_ENABLED}' 2>/dev/null || true)
echo "${VECTOR_ENABLED:-  (no controller configmap)}"
if [ "$VECTOR_ENABLED" = "true" ]; then pass "DATABASE_VECTOR_ENABLED=true"; else fail "DATABASE_VECTOR_ENABLED=true"; fi

echo "-- controller DB URL (expect postgres://, not sqlite) --"
kubectl --context "$CTX" get deploy -n "$NS" kagent-controller -o yaml 2>/dev/null \
  | grep -iE 'POSTGRES_DATABASE_URL|SQLITE|DATABASE_TYPE' | head -3

echo "-- pgvector extension (expect one row) --"
PGPOD=$(kubectl --context "$CTX" get pod -n "$NS" -l app.kubernetes.io/component=database -o name 2>/dev/null | head -1)
if [ -n "$PGPOD" ]; then
  VECTOR_EXTENSION=$(kubectl --context "$CTX" exec -n "$NS" "$PGPOD" -- \
    psql -U kagent -d kagent -tAc \
    "SELECT extname,extversion FROM pg_extension WHERE extname='vector';" 2>/dev/null || true)
  echo "${VECTOR_EXTENSION}"
  if echo "$VECTOR_EXTENSION" | grep -q '^vector|'; then pass "pgvector extension is present"; else fail "pgvector extension is present"; fi
else
  echo "  (no bundled postgres pod — external managed DB must be checked from an approved admin host)"
  fail "pgvector extension was not directly verified"
fi

echo "-- memory-enabled agents (spec.declarative.memory set) --"
kubectl --context "$CTX" get agents -n "$NS" -o json 2>/dev/null \
  | python3 -c "
import sys,json
for a in json.load(sys.stdin).get('items',[]):
    m=(a.get('spec',{}).get('declarative') or {}).get('memory')
    if m: print('  ',a['metadata']['name'],'-> memory.modelConfig=',m.get('modelConfig'),'ttlDays=',m.get('ttlDays'))
" 2>/dev/null || echo "  (none / parse skipped)"

echo "-- memory row count --"
[ -n "$PGPOD" ] && kubectl --context "$CTX" exec -n "$NS" "$PGPOD" -- \
  psql -U kagent -d kagent -tAc "SELECT count(*)||' memories' FROM memory;" 2>/dev/null
if [ "$FAILURES" -gt 0 ]; then
  echo "MEMORY_VERIFY: FAIL ($FAILURES check(s) failed)" >&2
  exit 1
fi
echo "MEMORY_VERIFY: PASS"
