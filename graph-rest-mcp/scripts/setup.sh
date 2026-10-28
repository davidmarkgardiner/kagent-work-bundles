#!/usr/bin/env bash
set -euo pipefail
: "${KUBE_CONTEXT:?Set the native Kagent target context}"
: "${IMAGE:?Set the image already loaded into Kind or available in a registry}"
: "${MODEL_CONFIG:?Set an existing native ModelConfig name}"
: "${HARNESS:?Set an existing native Harness name}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K=(kubectl --context "$KUBE_CONTEXT")
"${K[@]}" get crd agenttemplates.api.kagent.dev remotemcpservers.api.kagent.dev >/dev/null
"${K[@]}" -n kagent get modelconfig "$MODEL_CONFIG" >/dev/null
"${K[@]}" -n kagent get harness "$HARNESS" >/dev/null
OWNER="$("${K[@]}" get namespace graph-context-lab -o 'jsonpath={.metadata.labels.app\.kubernetes\.io/part-of}' --ignore-not-found)"
if "${K[@]}" get namespace graph-context-lab >/dev/null 2>&1 && [[ "$OWNER" != graph-rest-mcp ]]; then
  echo 'Refusing to take ownership of an existing namespace.' >&2
  exit 1
fi
for kind in agent agenttemplate remotemcpserver; do
  OBJECT_OWNER="$("${K[@]}" -n kagent get "$kind" graph-context-lab -o 'jsonpath={.metadata.labels.app\.kubernetes\.io/part-of}' --ignore-not-found)"
  if "${K[@]}" -n kagent get "$kind" graph-context-lab >/dev/null 2>&1 && [[ "$OBJECT_OWNER" != graph-rest-mcp ]]; then
    echo "Refusing to overwrite an unowned $kind." >&2
    exit 1
  fi
done
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 "$ROOT/scripts/render.py" --image "$IMAGE" --model-config "$MODEL_CONFIG" --harness "$HARNESS" > "$TMP/all.yaml"
python3 - "$TMP/all.yaml" > "$TMP/namespace.yaml" <<'PY'
import pathlib,sys
print(pathlib.Path(sys.argv[1]).read_text().split('\n---\n')[0])
PY
"${K[@]}" apply --dry-run=server -f "$TMP/namespace.yaml"
"${K[@]}" apply -f "$TMP/namespace.yaml"
"${K[@]}" apply --dry-run=server -f "$TMP/all.yaml"
"${K[@]}" apply -f "$TMP/all.yaml"
"${K[@]}" -n graph-context-lab rollout status deploy/graph-rest --timeout=180s
"${K[@]}" -n graph-context-lab rollout status deploy/graph-mcp --timeout=180s
"${K[@]}" -n kagent wait remotemcpserver/graph-context-lab --for=condition=Accepted --timeout=120s
"${K[@]}" -n kagent wait agent/graph-context-lab --for=condition=Ready --timeout=240s
