#!/usr/bin/env bash
# Level B: agent self-recall across sessions, fully local (Ollama embeddings).
# Seeds a memory under the runtime's INTERNAL agent_name, then proves a fresh
# A2A session's prefetch_memory retrieves it. Proven 2026-07-16.
#
# Prereq: install-memory.sh done, Ollama deployed with nomic-embed-text +
# a chat model, and the memory agent + ModelConfigs applied (examples/).
set -euo pipefail
CTX="${CTX:-kind-kagent-memory}"
NS="${NS:-kagent}"
CR_NAME="${CR_NAME:-memory-selflearn-agent}"   # the Agent CR metadata.name
USER="${USER_ID:-admin@kagent.dev}"
CPORT=18095; OPORT=21134
TOKEN="MAGENTA-$(date +%H%M%S)"
FACT="Production incident bridge code word is $TOKEN. Use it to authenticate on the incident call."
TMPDIR=$(mktemp -d)
OL=""
CF=""
cleanup() {
  [[ -n "${OL}" ]] && kill "${OL}" >/dev/null 2>&1 || true
  [[ -n "${CF}" ]] && kill "${CF}" >/dev/null 2>&1 || true
  rm -rf "${TMPDIR}"
}
trap cleanup EXIT

# The runtime keys native memory by an INTERNAL id, NOT the CR name:
#   {namespace}__NS__{name_with_hyphens_as_underscores}
POD=$(kubectl --context "$CTX" get pods -n "$NS" -o name | grep "$CR_NAME" | head -1)
[[ -n "${POD}" ]] || { echo "FATAL agent pod for ${CR_NAME} was not found" >&2; exit 1; }
AGENT_KEY=$(kubectl --context "$CTX" exec -n "$NS" "$POD" -- python3 -c \
  "from kagent.core import KAgentConfig as C; print(C().app_name)" 2>/dev/null | tr -d '\r')
echo "internal agent_name = $AGENT_KEY"
echo "token = $TOKEN"

kubectl --context "$CTX" port-forward -n "$NS" svc/ollama "$OPORT:11434" >"${TMPDIR}/ollama.log" 2>&1 & OL=$!
kubectl --context "$CTX" port-forward -n "$NS" svc/kagent-controller "$CPORT:8083" >"${TMPDIR}/controller.log" 2>&1 & CF=$!
sleep 4

echo "== 1. embed fact via Ollama nomic-embed-text (768-dim) =="
curl -sS "http://127.0.0.1:$OPORT/api/embeddings" -d "{\"model\":\"nomic-embed-text\",\"prompt\":\"$FACT\"}" \
  | python3 -c "import sys,json;e=json.load(sys.stdin)['embedding'];print('dims',len(e));open('${TMPDIR}/vector.json','w').write(json.dumps(e))"

echo "== 2. seed memory under internal key =="
python3 - "$AGENT_KEY" "$USER" "$FACT" "http://127.0.0.1:$CPORT" "${TMPDIR}/vector.json" <<'PY'
import sys,json,urllib.request
ag,user,fact,base,vector_file=sys.argv[1:6]
vec=json.load(open(vector_file))
body=json.dumps({"agent_name":ag,"user_id":user,"content":fact,"vector":vec,
                 "metadata":{"src":"levelB"},"ttl_days":7}).encode()
print("seed:",urllib.request.urlopen(base+"/api/memories/sessions",data=body,timeout=15).read().decode()[:80])
PY
kill "$OL" >/dev/null 2>&1 || true; OL=""

echo "== 3. FRESH session recall (prefetch retrieves; small CPU model is slow) =="
echo "   watch the agent log for: 'Successfully retrieved memories'"
curl -sS --max-time 400 -X POST "http://127.0.0.1:$CPORT/api/a2a/kagent/$CR_NAME/" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"r","method":"message/send","params":{"message":{"role":"user","messageId":"rm","parts":[{"kind":"text","text":"Recall from memory: what is my production incident bridge code word?"}]}}}' \
  | python3 -c "
import sys,json
d=json.load(sys.stdin); r=d.get('result',{})
def tx(o):
 out=[]
 if isinstance(o,dict):
  if o.get('kind')=='text' and 'text' in o: out.append(o['text'])
  for v in o.values(): out+=tx(v)
 elif isinstance(o,list):
  [out.extend(tx(v)) for v in o]
 return out
ts=[x for x in tx(r) if 'Recall from memory' not in x]
print('AGENT:', ts[-1] if ts else '(pending)')" 2>&1 || echo "(HTTP window may expire before slow inference finishes; check logs)"
kill "$CF" >/dev/null 2>&1 || true; CF=""

echo "== 4. retrieval proof in logs =="
if kubectl --context "$CTX" logs -n "$NS" deploy/"$CR_NAME" --tail=80 \
  | grep -q 'Successfully retrieved memories'; then
  echo "NATIVE_MEMORY_PREFETCH: passed"
else
  echo "FATAL fresh-session prefetch retrieval was not observed in agent logs" >&2
  exit 1
fi
echo "NOTE final natural-language echo of ${TOKEN} may remain slow on a CPU-only lab model; retrieval is the required proof."
