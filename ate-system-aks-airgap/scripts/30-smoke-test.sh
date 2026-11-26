#!/usr/bin/env bash
# Proves ate-system works: a stateful actor is suspended to object storage, every worker pod is
# deleted, and the actor is resumed. All three counters must continue. No kagent, no model.
# Creates and then removes namespace/atespace "ate-smoke". KEEP=true leaves it for debugging.
# SMOKE_IMAGE overrides the python image (for example with a digest reference).
set -euo pipefail
. "$(dirname "$0")/lib.sh"
NS=ate-smoke; PORT=18000
IMAGE="${SMOKE_IMAGE:-$REGISTRY/library/python@sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e}"   # actor images must be pinned by digest
ate() { kubectl-ate --context "$KUBE_CONTEXT" "$@"; }
PF=""
cleanup() {
  [ -n "$PF" ] && kill "$PF" 2>/dev/null || true
  [ "${KEEP:-false}" = true ] && return
  ate suspend actor smoke-1 -a $NS >/dev/null 2>&1 || true
  ate delete actor smoke-1 -a $NS >/dev/null 2>&1 || true
  ate delete actor-template smoke -a $NS >/dev/null 2>&1 || true
  ate delete atespace $NS >/dev/null 2>&1 || true
  k delete ns $NS --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

say "WorkerPool"
k apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata: {name: $NS}
---
apiVersion: ate.dev/v1
kind: WorkerPool
metadata: {name: smoke, namespace: $NS, labels: {workload: smoke}}
spec:
  replicas: 2
  workerImage: $REGISTRY/kagent-dev/substrate/ateworker-gvisor:v$SUBSTRATE_VERSION
  sandboxClasses: [{name: gvisor}]
  template:
    resources:
      limits: {cpu: "1", memory: 1Gi}
      requests: {cpu: 100m, memory: 1Gi}
YAML
for _ in $(seq 1 60); do k -n $NS get deploy smoke >/dev/null 2>&1 && break; sleep 3; done
k -n $NS rollout status deploy/smoke --timeout=5m

say "actor template (waits for the golden snapshot)"
ate create atespace $NS
APP='
import http.server, os
mem = 0
def bump(path):
    n = int(open(path).read()) + 1 if os.path.exists(path) else 1
    open(path, "w").write(str(n))
    return n
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global mem
        if self.path == "/readyz":
            body = "ok"
        else:
            mem += 1
            body = "memory=%d volume=%d rootfs=%d" % (mem, bump("/home/counter/n"), bump("/rootfs-n"))
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body.encode())
http.server.HTTPServer(("", 80), H).serve_forever()
'
python3 - "$NS" "$IMAGE" "$APP" <<'PY' | ate create actor-template -f -
import json, sys
ns, image, app = sys.argv[1:4]
print(json.dumps({
    'metadata': {'atespace': ns, 'name': 'smoke'},
    'workerSelector': {'matchLabels': {'workload': 'smoke'}},
    'containers': [{'name': 'counter', 'image': image, 'command': ['python', '-c', app],
                    'wakeupProbe': {'httpGet': {'path': '/readyz', 'port': 80}},
                    'volumeMounts': [{'name': 'data', 'mountPath': '/home/counter'}]}],
    'resources': {'limits': {'cpuMillicores': 1000, 'memoryBytes': 536870912}},
    'snapshotConfig': {'preferredFidelity': 'SNAPSHOT_FIDELITY_MEMORY'},
    'volumes': [{'name': 'data', 'durableDir': {}}]}))
PY
status=""
for _ in $(seq 1 90); do
  status="$(ate get actor-template smoke -a $NS -o yaml 2>/dev/null || true)"
  grep -qE 'goldenTag:|errorMessage:' <<<"$status" && break
  sleep 5
done
sed -n '/^status:/,/^[a-z]*:/p' <<<"$status"
if ! grep -q 'goldenTag:' <<<"$status"; then
  say "SMOKE TEST FAIL: no golden snapshot (run with KEEP=true to investigate)"; exit 1
fi

say "actor"
ate create actor smoke-1 -a $NS --template smoke
ate resume actor smoke-1 -a $NS
proxy() {
  [ -n "$PF" ] && kill "$PF" 2>/dev/null || true
  kubectl-ate --context "$KUBE_CONTEXT" proxy actor smoke-1 -a $NS $PORT:80 >/tmp/ate-proxy.log 2>&1 & PF=$!
  sleep 5
}
get() { curl -fsS --max-time 60 "http://127.0.0.1:$PORT/"; }
proxy
first="$(get)"; second="$(get)"; echo "$first"; echo "$second"

say "suspend to object storage, then delete every worker pod"
ate suspend actor smoke-1 -a $NS --mode sync
ate get actor smoke-1 -a $NS
k -n $NS delete pod --all --wait=true
k -n $NS rollout status deploy/smoke --timeout=5m

say "resume on a fresh worker"
ate resume actor smoke-1 -a $NS
proxy
third="$(get)"; echo "$third"

if [ "$second" = "memory=2 volume=2 rootfs=2" ] && [ "$third" = "memory=3 volume=3 rootfs=3" ]; then
  say "SMOKE TEST PASS: golden snapshot taken; memory, volume and root filesystem survived suspend and worker replacement"
else
  say "SMOKE TEST FAIL: expected 2/2/2 then 3/3/3"; exit 1
fi
