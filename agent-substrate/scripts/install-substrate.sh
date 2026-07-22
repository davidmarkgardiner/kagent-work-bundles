#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Agent Substrate — one-shot install on an isolated kind cluster.
#
# Stands up: substrate control+data plane (ate-system) + kagent with substrate
# integration + a demo SandboxAgent that runs as a gVisor actor.
#
# The model API key is read from the FIRST LINE OF STDIN so it never lands in
# shell history, process args, or this file. Example:
#
#   printf '%s\n' "$OPENROUTER_API_KEY" | bash scripts/install-substrate.sh
#
# Prereqs on the host: kind, kubectl, helm, a running Docker daemon,
# and >= ~8Gi free RAM (substrate ships 6x valkey + object store + worker pool).
# ---------------------------------------------------------------------------
set -euo pipefail

IFS= read -r -s MODEL_API_KEY
[[ -n "${MODEL_API_KEY}" ]] || { echo "FATAL model API key was empty" >&2; exit 2; }

CLUSTER="${CLUSTER:-kagent-substrate}"
CTX="kind-${CLUSTER}"
SUB_VER="${SUB_VER:-0.0.6}"      # agent-substrate chart version
KAGENT_VER="${KAGENT_VER:-0.9.9}" # kagent must be >= 0.9.7 for substrate
MODEL_NAME="${MODEL_NAME:-qwen/qwen3-next-80b-a3b-instruct:free}"
MODEL_BASE_URL="${MODEL_BASE_URL:-https://openrouter.ai/api/v1}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

for command in kind kubectl helm docker; do
  command -v "${command}" >/dev/null || {
    echo "FATAL required command not found: ${command}" >&2
    exit 2
  }
done

# Keep the model key out of process arguments and shell history. Helm still
# stores configured values in its release state, so this remains demo-only and
# must never be used for a work/production credential.
MODEL_KEY_FILE="$(mktemp)"
chmod 600 "${MODEL_KEY_FILE}"
trap 'rm -f "${MODEL_KEY_FILE}"' EXIT
printf '%s' "${MODEL_API_KEY}" >"${MODEL_KEY_FILE}"

log "=== STEP 1: isolated kind cluster ${CLUSTER} ==="
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER}"; then
  log "cluster exists, reusing"
else
  kind create cluster --name "${CLUSTER}" || { log "FATAL kind create failed"; exit 1; }
fi
kubectl --context "${CTX}" get nodes || exit 1

log "=== STEP 2: substrate CRDs v${SUB_VER} ==="
helm --kube-context "${CTX}" upgrade --install substrate-crds \
  oci://ghcr.io/kagent-dev/substrate/helm/substrate-crds \
  --version "${SUB_VER}" --namespace ate-system --create-namespace --wait --timeout 5m \
  || { log "FATAL substrate-crds failed"; exit 1; }

log "=== STEP 3: substrate control + data plane v${SUB_VER} ==="
helm --kube-context "${CTX}" upgrade --install substrate \
  oci://ghcr.io/kagent-dev/substrate/helm/substrate \
  --version "${SUB_VER}" --namespace ate-system --wait --timeout 12m \
  || log "WARN substrate did not fully converge (continuing to capture state)"
kubectl --context "${CTX}" get pods -n ate-system -o wide

log "=== STEP 4: kagent CRDs v${KAGENT_VER} ==="
helm --kube-context "${CTX}" upgrade --install kagent-crds \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
  --version "${KAGENT_VER}" --namespace kagent --create-namespace --wait --timeout 5m \
  || { log "FATAL kagent-crds failed"; exit 1; }

log "=== STEP 5: kagent v${KAGENT_VER} with substrate integration ==="
helm --kube-context "${CTX}" upgrade --install kagent \
  oci://ghcr.io/kagent-dev/kagent/helm/kagent \
  --version "${KAGENT_VER}" --namespace kagent --timeout 12m --wait \
  --set-file providers.openAI.apiKey="${MODEL_KEY_FILE}" \
  --set providers.default=openAI \
  --set registry=ghcr.io \
  --set controller.substrate.enabled=true \
  --set controller.substrate.ateApiEndpoint=dns:///api.ate-system.svc:443 \
  --set controller.substrate.ateApiInsecure=true \
  --set substrateWorkerPool.create=true \
  --set substrateWorkerPool.replicas=1 \
  --set substrateWorkerPool.ateomImage=ghcr.io/kagent-dev/substrate/ateom-gvisor:v${SUB_VER} \
  || log "WARN kagent did not fully converge (continuing)"

log "=== STEP 6: model endpoint reachable from the cluster ==="
kubectl --context "${CTX}" -n kagent create secret generic openrouter-api-key \
  --from-file=OPENROUTER_API_KEY="${MODEL_KEY_FILE}" \
  --dry-run=client -o yaml | kubectl --context "${CTX}" apply -f -

kubectl --context "${CTX}" apply -f - <<YAML
apiVersion: kagent.dev/v1alpha2
kind: ModelConfig
metadata:
  name: default-model-config
  namespace: kagent
spec:
  provider: OpenAI
  model: ${MODEL_NAME}
  apiKeySecret: openrouter-api-key
  apiKeySecretKey: OPENROUTER_API_KEY
  openAI:
    baseUrl: ${MODEL_BASE_URL}
    maxTokens: 1200
    temperature: "0.1"
YAML

log "=== STEP 7: deploy hello-substrate SandboxAgent ==="
kubectl --context "${CTX}" apply -f "$(dirname "$0")/../examples/sandboxagent-hello.yaml" \
  2>/dev/null || kubectl --context "${CTX}" apply -f - <<'YAML'
apiVersion: kagent.dev/v1alpha2
kind: SandboxAgent
metadata:
  name: hello-substrate
  namespace: kagent
spec:
  type: Declarative
  platform: substrate
  description: Tiny declarative agent running inside a substrate gVisor actor
  declarative:
    runtime: go
    modelConfig: default-model-config
    systemMessage: |
      You are a friendly assistant living inside an Agent Substrate sandbox.
      When asked who you are, say "I am hello-substrate, a Go ADK declarative
      agent running inside a gVisor actor."
  substrate:
    workerPoolRef:
      name: kagent-default
YAML

log "=== STEP 7.5: verify declarative Go ADK runtime registry ==="
# registry=ghcr.io is the source-level fix proven on the live run. Do not patch
# the generated ActorTemplate or scale the controller down: that hides a chart
# configuration error and is not a GitOps-safe work path.
log "waiting for ActorTemplate to appear ..."
for i in $(seq 1 30); do
  kubectl --context "${CTX}" -n kagent get actortemplate hello-substrate >/dev/null 2>&1 && break
  sleep 2
done
if kubectl --context "${CTX}" -n kagent get actortemplate hello-substrate >/dev/null 2>&1; then
  CUR_IMG=$(kubectl --context "${CTX}" -n kagent get actortemplate hello-substrate -o jsonpath='{.spec.containers[0].image}' 2>/dev/null)
  [[ "${CUR_IMG}" == ghcr.io/* ]] || {
    log "FATAL ActorTemplate uses unexpected runtime image: ${CUR_IMG}"
    log "Expected registry=ghcr.io to select a resolvable Go ADK image."
    exit 1
  }
else
  log "FATAL ActorTemplate was not created within 60 seconds"
  exit 1
fi

log "=== STEP 8: wait for SandboxAgent Ready ==="
kubectl --context "${CTX}" wait sandboxagent/hello-substrate -n kagent \
  --for=condition=Ready --timeout=5m || log "WARN sandboxagent not Ready in time"

log "=== FINAL STATE ==="
kubectl --context "${CTX}" get pods -n ate-system
kubectl --context "${CTX}" get pods -n kagent
kubectl --context "${CTX}" get sandboxagents -n kagent -o wide
log "=== DONE ==="
