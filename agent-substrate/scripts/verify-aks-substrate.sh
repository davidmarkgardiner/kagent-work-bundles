#!/usr/bin/env bash
# Read-only operational checks for Agent Substrate on an existing AKS cluster.
# It never creates, changes, or deletes Kubernetes resources.
set -euo pipefail

CONTEXT=""
KAGENT_NAMESPACE="kagent"
ATE_NAMESPACE="ate-system"
SANDBOX_AGENT=""
TIMEOUT="5m"
FAILURES=0

usage() {
  cat <<'EOF'
Usage: verify-aks-substrate.sh --context CONTEXT [options]

Options:
  --context CONTEXT              Required Kubernetes context.
  --kagent-namespace NAMESPACE   kagent namespace (default: kagent).
  --ate-namespace NAMESPACE      Agent Substrate namespace (default: ate-system).
  --sandboxagent NAME            Also require this SandboxAgent and ActorTemplate to be Ready.
  --timeout DURATION             kubectl rollout/wait timeout (default: 5m).
  -h, --help                     Show this help.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --context) CONTEXT="${2:?missing context}"; shift 2 ;;
    --kagent-namespace) KAGENT_NAMESPACE="${2:?missing namespace}"; shift 2 ;;
    --ate-namespace) ATE_NAMESPACE="${2:?missing namespace}"; shift 2 ;;
    --sandboxagent) SANDBOX_AGENT="${2:?missing SandboxAgent name}"; shift 2 ;;
    --timeout) TIMEOUT="${2:?missing timeout}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "${CONTEXT}" ]]; then
  echo "ERROR --context is required" >&2
  usage >&2
  exit 2
fi

command -v kubectl >/dev/null || { echo "ERROR kubectl is required" >&2; exit 2; }
k() { kubectl --context "${CONTEXT}" "$@"; }
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }

check() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "${description}"
  else
    fail "${description}"
  fi
}

rollout_all() {
  local resource="$1" namespace="$2" items item
  items="$(k -n "${namespace}" get "${resource}" -o name 2>/dev/null || true)"
  if [[ -z "${items}" ]]; then
    pass "no ${resource} resources in ${namespace}"
    return
  fi
  while IFS= read -r item; do
    [[ -z "${item}" ]] && continue
    check "${namespace} ${item} rolled out" k -n "${namespace}" rollout status "${item}" --timeout="${TIMEOUT}"
  done <<< "${items}"
}

workerpools_ready() {
  local rows namespace name desired replicas
  rows="$(k get workerpool.ate.dev -A \
    -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.status.desiredReplicas}{"\t"}{.status.replicas}{"\n"}{end}' \
    2>/dev/null || true)"
  if [[ -z "${rows}" ]]; then
    fail "at least one WorkerPool exists"
    return
  fi
  while IFS=$'\t' read -r namespace name desired replicas; do
    [[ -z "${name}" ]] && continue
    if [[ "${desired}" =~ ^[1-9][0-9]*$ && "${replicas}" == "${desired}" ]]; then
      pass "WorkerPool ${namespace}/${name} has ${replicas}/${desired} replicas"
    else
      fail "WorkerPool ${namespace}/${name} is not ready (desired=${desired:-unknown}, replicas=${replicas:-unknown})"
    fi
  done <<< "${rows}"
}

echo "==> Checking Kubernetes API access"
check "context ${CONTEXT} is reachable" k version --request-timeout=15s

echo "==> Checking required CRDs"
check "SandboxAgent CRD exists" k get crd sandboxagents.kagent.dev
check "Agent Substrate WorkerPool CRD exists" k get crd workerpools.ate.dev
check "Agent Substrate ActorTemplate CRD exists" k get crd actortemplates.ate.dev

echo "==> Checking Agent Substrate control/data plane in ${ATE_NAMESPACE}"
check "namespace ${ATE_NAMESPACE} exists" k get namespace "${ATE_NAMESPACE}"
rollout_all deployment "${ATE_NAMESPACE}"
rollout_all daemonset "${ATE_NAMESPACE}"
rollout_all statefulset "${ATE_NAMESPACE}"
workerpools_ready

echo "==> Checking kagent integration in ${KAGENT_NAMESPACE}"
check "namespace ${KAGENT_NAMESPACE} exists" k get namespace "${KAGENT_NAMESPACE}"
check "kagent controller deployment exists" k -n "${KAGENT_NAMESPACE}" get deployment kagent-controller
check "kagent controller rollout is healthy" k -n "${KAGENT_NAMESPACE}" rollout status deployment/kagent-controller --timeout="${TIMEOUT}"

if [[ -n "${SANDBOX_AGENT}" ]]; then
  echo "==> Checking SandboxAgent ${KAGENT_NAMESPACE}/${SANDBOX_AGENT}"
  check "SandboxAgent exists" k -n "${KAGENT_NAMESPACE}" get sandboxagent "${SANDBOX_AGENT}"
  check "SandboxAgent is Ready" k -n "${KAGENT_NAMESPACE}" wait "sandboxagent/${SANDBOX_AGENT}" --for=condition=Ready --timeout="${TIMEOUT}"
  check "generated ActorTemplate exists" k -n "${KAGENT_NAMESPACE}" get actortemplate "${SANDBOX_AGENT}"
  check "generated ActorTemplate golden snapshot is Ready" bash -c \
    "test \"\$(kubectl --context '$CONTEXT' -n '$KAGENT_NAMESPACE' get actortemplate '$SANDBOX_AGENT' -o jsonpath='{.status.phase}')\" = Ready"
fi

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "AKS_SUBSTRATE_VERIFY: FAIL (${FAILURES} check(s) failed)" >&2
  exit 1
fi

echo "AKS_SUBSTRATE_VERIFY: PASS"
