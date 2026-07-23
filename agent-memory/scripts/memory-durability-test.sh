#!/usr/bin/env bash
# Level A: durable native-memory proof via the controller REST API.
# store -> list -> vector-search -> isolation -> RESTART SURVIVAL.
# No embedding model needed here (caller supplies the 768-dim vector), so this
# runs even before an embedding ModelConfig exists. Proven 2026-07-16.
set -euo pipefail
CTX="${CTX:-kind-kagent-memory}"
NS="${NS:-kagent}"
PORT="${PORT:-18085}"
AGENT="memory-durability-agent"
USER="lab-user-$(date +%Y%m%d%H%M%S)"
B="http://127.0.0.1:$PORT"
PGPOD=$(kubectl --context "$CTX" get pod -n "$NS" -l app.kubernetes.io/component=database -o name | head -1)
[[ -n "${PGPOD}" ]] || { echo "FATAL bundled Postgres pod was not found" >&2; exit 1; }
PF=""

pf(){ kubectl --context "$CTX" port-forward -n "$NS" svc/kagent-controller "$PORT:8083" >/tmp/dur-pf.log 2>&1 & PF=$!; sleep 3; }
stoppf(){ [[ -n "${PF}" ]] && kill "$PF" >/dev/null 2>&1 || true; PF=""; }
trap stoppf EXIT

echo "== backend =="
kubectl --context "$CTX" get cm -n "$NS" kagent-controller -o jsonpath='DATABASE_VECTOR_ENABLED={.data.DATABASE_VECTOR_ENABLED}{"\n"}'
kubectl --context "$CTX" exec -n "$NS" "$PGPOD" -- psql -U kagent -d kagent -tAc \
  "SELECT 'pgvector '||extversion FROM pg_extension WHERE extname='vector';"

pf
VEC=$(python3 -c "print('['+','.join(['0.0013']*768)+']')")
echo "== 1. store =="
curl -sS -X POST "$B/api/memories/sessions" -H 'Content-Type: application/json' \
  -d "{\"agent_name\":\"$AGENT\",\"user_id\":\"$USER\",\"content\":\"Lab fact: INC-7788 root cause was a wedged pgvector HNSW index; fix REINDEX. Token DURABLE-MEMORY-XT.\",\"vector\":$VEC,\"metadata\":{\"src\":\"levelA\"},\"ttl_days\":7}" | head -c 200; echo
echo "== 2. list =="; curl -sS "$B/api/memories?agent_name=$AGENT&user_id=$USER" | head -c 400; echo
echo "== 3. vector search (expect score ~1) =="
curl -sS -X POST "$B/api/memories/search" -H 'Content-Type: application/json' \
  -d "{\"agent_name\":\"$AGENT\",\"user_id\":\"$USER\",\"vector\":$VEC,\"limit\":5,\"min_score\":0.0}" | head -c 300; echo
echo "== 4. isolation (both expect []) =="
curl -sS "$B/api/memories?agent_name=${AGENT}-other&user_id=$USER"; echo
curl -sS "$B/api/memories?agent_name=$AGENT&user_id=${USER}-other"; echo
stoppf

echo "== 5. Postgres rows (durable, not in-memory) =="
kubectl --context "$CTX" exec -n "$NS" "$PGPOD" -- psql -U kagent -d kagent -tAc "SELECT count(*) FROM memory;"

echo "== 6. RESTART SURVIVAL: destroy Postgres + controller pods =="
kubectl --context "$CTX" delete pod -n "$NS" -l app.kubernetes.io/component=database --wait=true
kubectl --context "$CTX" rollout restart deploy/kagent-controller -n "$NS"
kubectl --context "$CTX" rollout status deploy/kagent-postgresql -n "$NS" --timeout=180s | tail -1
kubectl --context "$CTX" rollout status deploy/kagent-controller -n "$NS" --timeout=180s | tail -1

echo "== 7. recall AFTER restart (same memory should return) =="
pf
RECALL=$(curl -fsS "$B/api/memories?agent_name=$AGENT&user_id=$USER")
printf '%s\n' "$RECALL" | head -c 400; echo
printf '%s' "$RECALL" | grep -q 'DURABLE-MEMORY-XT' || {
  echo "FATAL durable memory was not returned after restart" >&2
  exit 1
}
stoppf
echo "NATIVE_MEMORY_RESTART_SURVIVAL: passed"
