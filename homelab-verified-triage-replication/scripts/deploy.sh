#!/usr/bin/env bash
# Deploy the evidence-first triage path.
#
# Read-only prerequisites are checked first and the script refuses to run if any
# are missing, so you find out before half the stack is applied.
#
#   bash scripts/deploy.sh --context <kubectl-context>
#
# It applies the native Kustomize bundle: namespace, worker Vector, worker
# Alloy, management Argo backend, and concurrency semaphore. Nothing here
# creates a Secret — the two Secrets below must already exist and are
# referenced, never inlined.
set -euo pipefail

CONTEXT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --context) CONTEXT="${2:?--context needs a value}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$CONTEXT" ]; then
  echo "ERROR: --context is required. A shell's default context is not proof of intent." >&2
  echo "       Current default would be: $(kubectl config current-context 2>/dev/null || echo '<none>')" >&2
  exit 2
fi
K="kubectl --context $CONTEXT"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Target =="
$K config current-context >/dev/null
echo "context: $CONTEXT"
$K get nodes -o name | head -5
echo

echo "== Preflight =="
fail=0
check() { # name, command...
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  ok      $name"
  else
    echo "  MISSING $name"
    fail=1
  fi
}
check "namespace argo-events"                 $K get ns argo-events
check "namespace monitoring"                  $K get ns monitoring
check "namespace kagent"                      $K get ns kagent
check "secret argo-events/confluent-credentials" $K -n argo-events get secret confluent-credentials
check "secret argo-events/gitlab-credentials"    $K -n argo-events get secret gitlab-credentials
check "serviceaccount argo-events/argo-events-sa" $K -n argo-events get sa argo-events-sa
check "serviceaccount monitoring/alloy"       $K -n monitoring get sa alloy
check "eventbus argo-events/default"          $K -n argo-events get eventbus default
check "CRD workflowtemplates"                 $K get crd workflowtemplates.argoproj.io
check "CRD sensors"                           $K get crd sensors.argoproj.io
check "kagent read-only agent"                $K -n kagent get agent k8s-readonly-agent

# Secret KEY names matter as much as the Secret existing.
for kv in confluent-credentials:bootstrap confluent-credentials:key confluent-credentials:secret \
          gitlab-credentials:url gitlab-credentials:token gitlab-credentials:project-id; do
  s="${kv%%:*}"; k="${kv##*:}"
  if $K -n argo-events get secret "$s" -o "jsonpath={.data.$k}" 2>/dev/null | grep -q .; then
    echo "  ok      secret $s has key '$k'"
  else
    echo "  MISSING secret $s key '$k'"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "Preflight failed. Nothing was applied. Create the missing prerequisites first." >&2
  exit 1
fi
echo

echo "== Apply =="
$K apply -k "$HERE/config"
echo

echo "== Rollout =="
$K -n argo-events rollout status deploy/vector-telemetry-triage --timeout=180s
$K -n monitoring  rollout status deploy/alloy-vector-triage      --timeout=180s
echo
echo "Deployed. Next:"
echo "  bash scripts/verify.sh    --context $CONTEXT   # health + wiring, read-only"
echo "  bash scripts/smoke-test.sh --context $CONTEXT  # fire fixtures, prove end to end"
