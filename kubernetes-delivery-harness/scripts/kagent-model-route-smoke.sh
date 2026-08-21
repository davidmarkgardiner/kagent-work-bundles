#!/usr/bin/env bash
# Prove one ModelConfig serves a real kagent Agent, then remove the test Agent.
set -euo pipefail

MODEL_CONFIG=""
PROVIDER=""
EXPECTED=""
CONTEXT=""
NAMESPACE="kagent"
TIMEOUT=240

usage() {
  cat <<'EOF'
Usage: kagent-model-route-smoke.sh --model-config NAME --provider NAME --expected MARKER [options]

Creates a disposable, tool-less kagent Agent, waits for it to serve, calls it
through A2A, checks the exact marker, then deletes it. This does not inspect or
print API credentials.

Options:
  --model-config NAME   Existing ModelConfig in the kagent namespace (required)
  --provider NAME       Safe name used in the disposable Agent name (required)
  --expected MARKER     Exact expected response marker (required)
  --context CONTEXT     Explicit kubectl context
  --namespace NS        kagent namespace (default: kagent)
  --timeout SECONDS     Readiness/A2A timeout (default: 240)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-config) MODEL_CONFIG="$2"; shift 2 ;;
    --provider) PROVIDER="$2"; shift 2 ;;
    --expected) EXPECTED="$2"; shift 2 ;;
    --context) CONTEXT="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$MODEL_CONFIG" && -n "$PROVIDER" && -n "$EXPECTED" ]] || { usage >&2; exit 2; }
[[ "$PROVIDER" =~ ^[a-z0-9-]+$ ]] || { echo "--provider must be lowercase letters, numbers, or hyphens" >&2; exit 2; }
for binary in kubectl jq; do
  command -v "$binary" >/dev/null || { echo "required binary missing: $binary" >&2; exit 2; }
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
KUBECTL=(kubectl)
[[ -n "$CONTEXT" ]] && KUBECTL+=(--context "$CONTEXT")
AGENT="model-smoke-${PROVIDER}-$(date +%Y%m%d%H%M%S)"
MANIFEST="$(mktemp "${TMPDIR:-/tmp}/kagent-model-smoke.XXXXXX.yaml")"
RESULT="$(mktemp "${TMPDIR:-/tmp}/kagent-model-smoke.XXXXXX.json")"

cleanup() {
  "${KUBECTL[@]}" -n "$NAMESPACE" delete agent "$AGENT" --ignore-not-found --wait=true >/dev/null 2>&1 || true
  rm -f "$MANIFEST" "$RESULT"
}
trap cleanup EXIT

"${KUBECTL[@]}" -n "$NAMESPACE" get modelconfig "$MODEL_CONFIG" >/dev/null
cat > "$MANIFEST" <<EOF
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata:
  name: ${AGENT}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/part-of: kagent-model-route-smoke
    kagent-model-smoke.dev/provider: ${PROVIDER}
spec:
  type: Declarative
  description: Disposable read-only ModelConfig smoke test.
  declarative:
    modelConfig: ${MODEL_CONFIG}
    runtime: python
    deployment:
      replicas: 1
      resources:
        requests: {cpu: 100m, memory: 384Mi}
        limits: {cpu: "2", memory: 1Gi}
    a2aConfig:
      skills:
        - id: model-route-smoke
          name: Model route smoke
          description: Return a fixed marker through the configured model route.
          inputModes: [text]
          outputModes: [text]
          tags: [smoke, model-route, read-only]
    systemMessage: |
      You are a disposable read-only model-route smoke-test agent.
      Reply with exactly ${EXPECTED}.
    tools: []
EOF

"${KUBECTL[@]}" apply --dry-run=server -f "$MANIFEST" >/dev/null
"${KUBECTL[@]}" apply -f "$MANIFEST" >/dev/null
"${KUBECTL[@]}" -n "$NAMESPACE" wait --for=condition=Accepted "agent/${AGENT}" --timeout="${TIMEOUT}s" >/dev/null
"${KUBECTL[@]}" -n "$NAMESPACE" wait --for=condition=Ready "agent/${AGENT}" --timeout="${TIMEOUT}s" >/dev/null

INVOKE=("$REPO_ROOT/scripts/kagent-a2a-invoke.sh" --agent "$AGENT" --ns "$NAMESPACE" --timeout "$TIMEOUT" --json --text "Reply with exactly: ${EXPECTED}")
[[ -n "$CONTEXT" ]] && INVOKE+=(--context "$CONTEXT")
"${INVOKE[@]}" > "$RESULT"
ACTUAL="$(jq -r '.text' "$RESULT")"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo "FAIL expected '$EXPECTED', got '$ACTUAL'" >&2; exit 1; }
printf 'PASS provider=%s model_config=%s agent=%s marker=%s\n' "$PROVIDER" "$MODEL_CONFIG" "$AGENT" "$EXPECTED"
