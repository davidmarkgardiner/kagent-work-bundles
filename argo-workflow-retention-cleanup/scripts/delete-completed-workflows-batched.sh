#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Delete old terminal Argo Workflows in controlled batches.

This is faster than `argo delete --completed` for very large backlogs because it
deletes many workflow names per kubectl request. It still uses conservative
batching and a parallelism cap to avoid overwhelming the API server.

Usage:
  delete-completed-workflows-batched.sh --context <ctx> --older 14d --dry-run
  delete-completed-workflows-batched.sh --context <ctx> --older 14d --yes

Options:
  --context <name>       kubeconfig context to use. Strongly recommended.
  --namespace <name>     namespace to clean. Default: all namespaces.
  --older <duration>     delete terminal workflows older than duration. Default: 14d.
                         Supports s, m, h, d, for example 30m, 12h, 14d.
  --phases <csv>         terminal phases to include. Default: Succeeded,Failed,Error.
  --selector <selector>  additional label selector passed to kubectl get.
  --batch-size <n>       workflow names per kubectl delete request. Default: 200.
  --parallel <n>         delete requests to run at a time. Default: 4.
  --dry-run             list count and sample only; do not delete.
  --yes                 required for deletion.
  -h, --help            show this help.

Examples:
  # First pass: see what would be deleted.
  ./scripts/delete-completed-workflows-batched.sh \
    --context {{MGMT_KUBE_CONTEXT}} \
    --older 14d \
    --dry-run

  # Actual 14-day cleanup, four delete calls in parallel, 200 names per call.
  ./scripts/delete-completed-workflows-batched.sh \
    --context {{MGMT_KUBE_CONTEXT}} \
    --older 14d \
    --batch-size 200 \
    --parallel 4 \
    --yes

  # Keep failed/error workflows longer; delete only successful workflows older than 1d.
  ./scripts/delete-completed-workflows-batched.sh \
    --context {{MGMT_KUBE_CONTEXT}} \
    --older 1d \
    --phases Succeeded \
    --yes
EOF
}

KUBE_CONTEXT=""
NAMESPACE=""
OLDER="14d"
PHASES="Succeeded,Failed,Error"
SELECTOR=""
BATCH_SIZE=200
PARALLEL=4
DRY_RUN=false
YES=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --context)
      KUBE_CONTEXT="${2:?--context requires a value}"
      shift 2
      ;;
    --namespace|-n)
      NAMESPACE="${2:?--namespace requires a value}"
      shift 2
      ;;
    --older)
      OLDER="${2:?--older requires a value}"
      shift 2
      ;;
    --phases)
      PHASES="${2:?--phases requires a value}"
      shift 2
      ;;
    --selector|-l)
      SELECTOR="${2:?--selector requires a value}"
      shift 2
      ;;
    --batch-size)
      BATCH_SIZE="${2:?--batch-size requires a value}"
      shift 2
      ;;
    --parallel)
      PARALLEL="${2:?--parallel requires a value}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --yes)
      YES=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

duration_to_seconds() {
  local value="$1"
  local number unit
  if ! [[ "$value" =~ ^([0-9]+)([smhd])$ ]]; then
    echo "invalid duration '$value'; use 30m, 12h, 14d, etc." >&2
    exit 2
  fi
  number="${BASH_REMATCH[1]}"
  unit="${BASH_REMATCH[2]}"
  case "$unit" in
    s) echo "$number" ;;
    m) echo $((number * 60)) ;;
    h) echo $((number * 3600)) ;;
    d) echo $((number * 86400)) ;;
  esac
}

require_cmd kubectl
require_cmd jq

if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [ "$BATCH_SIZE" -lt 1 ]; then
  echo "--batch-size must be a positive integer" >&2
  exit 2
fi

if ! [[ "$PARALLEL" =~ ^[0-9]+$ ]] || [ "$PARALLEL" -lt 1 ]; then
  echo "--parallel must be a positive integer" >&2
  exit 2
fi

if [ "$DRY_RUN" = false ] && [ "$YES" = false ]; then
  echo "refusing to delete without --yes; run with --dry-run first" >&2
  exit 2
fi

KUBECTL_ARGS=()
if [ -n "$KUBE_CONTEXT" ]; then
  KUBECTL_ARGS+=(--context "$KUBE_CONTEXT")
fi

if [ -n "$NAMESPACE" ]; then
  KUBECTL_SCOPE=(-n "$NAMESPACE")
else
  KUBECTL_SCOPE=(-A)
fi

if [ -n "$SELECTOR" ]; then
  KUBECTL_SELECTOR=(-l "$SELECTOR")
else
  KUBECTL_SELECTOR=()
fi

OLDER_SECONDS="$(duration_to_seconds "$OLDER")"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

CANDIDATES="$TMPDIR/candidates.tsv"

echo "Context: ${KUBE_CONTEXT:-$(kubectl config current-context 2>/dev/null || echo '<none>')}"
echo "Namespace: ${NAMESPACE:-all}"
echo "Older than: $OLDER (${OLDER_SECONDS}s)"
echo "Phases: $PHASES"
echo "Batch size: $BATCH_SIZE"
echo "Parallel delete calls: $PARALLEL"
echo

kubectl "${KUBECTL_ARGS[@]}" get workflows.argoproj.io "${KUBECTL_SCOPE[@]}" \
  "${KUBECTL_SELECTOR[@]}" \
  --chunk-size 500 \
  -o json \
  | jq -r --argjson older "$OLDER_SECONDS" --arg phases "$PHASES" '
      ($phases | split(",") | map(gsub("^\\s+|\\s+$"; ""))) as $allowed
      | .items[]
      | (.status.phase // "Unknown") as $phase
      | select($allowed | index($phase))
      | (.status.finishedAt // .metadata.creationTimestamp // "") as $finished
      | select($finished != "")
      | select(($finished | fromdateiso8601) < (now - $older))
      | [
          .metadata.namespace,
          .metadata.name,
          $phase,
          $finished
        ] | @tsv
    ' > "$CANDIDATES"

TOTAL="$(wc -l < "$CANDIDATES" | tr -d ' ')"

if [ "$TOTAL" = "0" ]; then
  echo "No matching workflows found."
  exit 0
fi

echo "Matching workflows: $TOTAL"
echo
echo "Sample:"
sed -n '1,20p' "$CANDIDATES" | column -t -s $'\t' || sed -n '1,20p' "$CANDIDATES"
echo

if [ "$DRY_RUN" = true ]; then
  echo "Dry-run only. No workflows deleted."
  exit 0
fi

echo "Deleting matching workflows..."

cut -f1 "$CANDIDATES" | sort -u > "$TMPDIR/namespaces.txt"

delete_chunk() {
  local namespace="$1"
  local chunk_file="$2"
  local names

  names="$(tr '\n' ' ' < "$chunk_file")"
  if [ -z "${names// /}" ]; then
    return 0
  fi

  # shellcheck disable=SC2086
  kubectl "${KUBECTL_ARGS[@]}" -n "$namespace" delete workflows.argoproj.io \
    $names \
    --ignore-not-found \
    --wait=false
}

active=0
while IFS= read -r namespace; do
  ns_dir="$TMPDIR/ns-$namespace"
  mkdir -p "$ns_dir"
  awk -F '\t' -v ns="$namespace" '$1 == ns { print $2 }' "$CANDIDATES" \
    | split -l "$BATCH_SIZE" - "$ns_dir/chunk-"

  for chunk in "$ns_dir"/chunk-*; do
    [ -s "$chunk" ] || continue
    delete_chunk "$namespace" "$chunk" &
    active=$((active + 1))
    if [ "$active" -ge "$PARALLEL" ]; then
      wait
      active=0
    fi
  done
done < "$TMPDIR/namespaces.txt"

wait

echo
echo "Delete requests submitted. Recheck with:"
if [ -n "$NAMESPACE" ]; then
  echo "  kubectl ${KUBE_CONTEXT:+--context $KUBE_CONTEXT} -n $NAMESPACE get workflows.argoproj.io"
else
  echo "  kubectl ${KUBE_CONTEXT:+--context $KUBE_CONTEXT} get workflows.argoproj.io -A --no-headers | wc -l"
fi
