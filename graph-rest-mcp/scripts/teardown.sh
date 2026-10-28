#!/usr/bin/env bash
set -euo pipefail
: "${KUBE_CONTEXT:?Set the context used for setup}"
K=(kubectl --context "$KUBE_CONTEXT")
delete_owned() {
  local kind="$1" name="$2" owner
  owner="$("${K[@]}" -n kagent get "$kind" "$name" -o 'jsonpath={.metadata.labels.app\.kubernetes\.io/part-of}' --ignore-not-found)"
  if [[ "$owner" == graph-rest-mcp ]]; then
    "${K[@]}" -n kagent delete "$kind" "$name"
  elif [[ -n "$owner" ]]; then
    echo "Refusing to delete unowned $kind." >&2
    exit 1
  fi
}
for kind in agent agenttemplate remotemcpserver harness workerpool.ate.dev; do
  delete_owned "$kind" graph-context-lab
done
delete_owned modelconfig graph-context-lab-local
OWNER="$("${K[@]}" get namespace graph-context-lab -o 'jsonpath={.metadata.labels.app\.kubernetes\.io/part-of}' --ignore-not-found)"
if [[ "$OWNER" == graph-rest-mcp ]]; then
  "${K[@]}" delete namespace graph-context-lab
elif [[ -n "$OWNER" ]]; then
  echo 'Refusing to delete unowned namespace.' >&2
  exit 1
fi
