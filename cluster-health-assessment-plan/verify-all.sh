#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_CONTEXT="${1:-}"
CAGE_CONTEXT="${2:-}"
GO_BUILD_CACHE="$(mktemp -d "${TMPDIR:-/tmp}/cluster-health-go-cache.XXXXXX")"

cleanup() {
  rm -rf -- "$GO_BUILD_CACHE"
}
trap cleanup EXIT

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$ROOT_DIR/b1" -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$ROOT_DIR/b3" -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$ROOT_DIR/b4" -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT_DIR/fox-mesh/verify.py"
PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT_DIR/workplace-bundle/scripts/verify.py"
(cd "$ROOT_DIR/b2/intake" && GOCACHE="$GO_BUILD_CACHE" go test ./...)
ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import json
import os
from pathlib import Path
from jsonschema import Draft202012Validator
for schema_path in sorted((Path(os.environ["ROOT_DIR"]) / "contracts").glob("*.schema.json")):
    Draft202012Validator.check_schema(json.loads(schema_path.read_text()))
PY

for component in b1 b2/worker b2/agent-cage b3 b4 fox-mesh single-cluster workplace-bundle/worker workplace-bundle/manager; do
  kubectl kustomize "$ROOT_DIR/$component" >/dev/null
done

qualification="$(PYTHONDONTWRITEBYTECODE=1 python3 "$ROOT_DIR/b1/accelerated_qualification.py")"
[[ "$(jq -r .slot_count <<<"$qualification")" == "20" ]]
[[ "$(jq -r .substitutes_for_real_elapsed_soak <<<"$qualification")" == "false" ]]

if [[ -n "$WORKER_CONTEXT" ]]; then
  kubectl --context "$WORKER_CONTEXT" apply --dry-run=server -k "$ROOT_DIR/b1" >/dev/null
  kubectl --context "$WORKER_CONTEXT" apply --dry-run=server -k "$ROOT_DIR/b2/worker" >/dev/null
  publisher_sa="system:serviceaccount:cluster-health-system:cluster-health-publisher"
  [[ "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$publisher_sa" get configmaps -n cluster-health-system)" == "yes" ]]
  [[ "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$publisher_sa" get secrets -n cluster-health-system)" == "no" ]]
  [[ "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$publisher_sa" list pods -A)" == "no" ]]
  snapshot_name="$(kubectl --context "$WORKER_CONTEXT" -n cluster-health-system get configmap cluster-health-latest -o jsonpath='{.data.pointer\.json}' | jq -r .snapshot)"
  kubectl --context "$WORKER_CONTEXT" -n cluster-health-system get configmap "$snapshot_name" -o jsonpath='{.data.snapshot\.json}' | \
    SNAPSHOT_SCHEMA="$ROOT_DIR/contracts/snapshot.schema.json" python3 -c 'import json,os,sys,jsonschema; jsonschema.validate(json.load(sys.stdin), json.load(open(os.environ["SNAPSHOT_SCHEMA"])))'
  if kubectl --context "$WORKER_CONTEXT" get namespace agent-health-system >/dev/null 2>&1; then
    kubectl --context "$WORKER_CONTEXT" apply --dry-run=server -k "$ROOT_DIR/single-cluster" >/dev/null
    [[ "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$publisher_sa" get secrets -n agent-health-system)" == "no" ]]
    [[ "$(kubectl --context "$WORKER_CONTEXT" auth can-i --as="$publisher_sa" list pods -n agent-health-system)" == "no" ]]
  fi
fi

if [[ -n "$CAGE_CONTEXT" ]]; then
  kubectl --context "$CAGE_CONTEXT" apply --dry-run=server -k "$ROOT_DIR/b2/agent-cage" >/dev/null
  kubectl --context "$CAGE_CONTEXT" apply --dry-run=server -k "$ROOT_DIR/b3" >/dev/null
  kubectl --context "$CAGE_CONTEXT" apply --dry-run=server -k "$ROOT_DIR/b4" >/dev/null
fi

echo "Cluster-health lab package verification passed"
