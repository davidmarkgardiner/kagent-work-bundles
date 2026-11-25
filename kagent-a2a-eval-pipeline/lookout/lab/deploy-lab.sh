#!/usr/bin/env bash
# LAB/TEST ONLY. Deploys Lookout against a MOCK GitLab so the agent path can be tested end to end.
# Run where kubectl can reach the lab cluster. Idempotent. Creates only lookout-* objects and the mr-security-review agent in $NS.
#   KUBE_CONTEXT=kind-kagent-alpha17 KAGENT_API=1x HARNESS=aks-docs-v1 MODEL_CONFIG=glm-coding ./deploy-lab.sh   # kagent 1.x
#   KUBE_CONTEXT=<ctx> KAGENT_API=0.7 MODEL_CONFIG=<mc> ./deploy-lab.sh                                          # kagent 0.7.x
#   KUBE_CONTEXT=<ctx> ./deploy-lab.sh down                                                                      # remove everything it made
# Real GitLab instead of the mock (the lookout-gitlab-token Secret must already exist; it is never created or printed here):
#   LOOKOUT_GITLAB_URL=https://gitlab.com LOOKOUT_PROJECTS=group/project KUBE_CONTEXT=<ctx> ... ./deploy-lab.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LOOKOUT="$(dirname "$HERE")"
CTX="${KUBE_CONTEXT:?set KUBE_CONTEXT to the lab context (never a work or production context)}"
NS="${NS:-kagent}"
API="${KAGENT_API:-0.7}"
k() { kubectl --context "$CTX" -n "$NS" "$@"; }

if [ "${1:-}" = "down" ]; then
  # Name both API groups: on 1.x a bare `agent` resolves to api.kagent.dev and kagent.dev objects are inert.
  for r in agents.api.kagent.dev agents.kagent.dev remotemcpservers.api.kagent.dev remotemcpservers.kagent.dev; do
    case "$r" in agents.*) n=mr-security-review ;; *) n=lookout-gitlab-mcp ;; esac
    k delete "$r" "$n" --ignore-not-found 2>/dev/null || true
  done
  k delete deploy,svc lookout-gitlab-mcp lookout-mock-gitlab --ignore-not-found
  k delete configmap lookout-gitlab-mcp lookout-mock-gitlab --ignore-not-found
  k delete secret lookout-gitlab-token --ignore-not-found
  echo "lookout lab objects removed"; exit 0
fi

MODEL_CONFIG="${MODEL_CONFIG:?set MODEL_CONFIG to an existing ModelConfig in $NS}"
if [ "$API" = "1x" ]; then
  HARNESS="${HARNESS:?set HARNESS to an approved Harness for kagent 1.x}"
  AGENT_RES=agents.api.kagent.dev; MODEL_RES=modelconfigs.api.kagent.dev
  AGENT_FILE="$LOOKOUT/manifests/mr-security-review-agent-v1alpha3.yaml"
  # Only the RemoteMCPServer document carries a kagent apiVersion; the Deployment and Service are unchanged.
  fix_api() { sed -e 's#apiVersion: kagent.dev/v1alpha2#apiVersion: api.kagent.dev/v1alpha3#'; }
else
  AGENT_RES=agents.kagent.dev; MODEL_RES=modelconfigs.kagent.dev
  AGENT_FILE="$LOOKOUT/manifests/mr-security-review-agent.yaml"
  fix_api() { cat; }
fi

k get "$MODEL_RES" "$MODEL_CONFIG" >/dev/null   # fail early if it does not exist
k create configmap lookout-gitlab-mcp --from-file=server.py="$LOOKOUT/gitlab_review_mcp.py" --dry-run=client -o yaml | k apply -f -
if [ -n "${LOOKOUT_GITLAB_URL:-}" ]; then
  # Real GitLab: no mock, no dummy token. The Secret must be created beforehand by a person.
  : "${LOOKOUT_PROJECTS:?set LOOKOUT_PROJECTS (comma list) when using a real GitLab}"
  k get secret lookout-gitlab-token >/dev/null || { echo "create Secret lookout-gitlab-token first" >&2; exit 1; }
  GL_URL="$LOOKOUT_GITLAB_URL"; GL_PROJECTS="$LOOKOUT_PROJECTS"; ROLL="deploy/lookout-gitlab-mcp"
else
  k create configmap lookout-mock-gitlab --from-file=server.py="$HERE/mock_gitlab.py" --dry-run=client -o yaml | k apply -f -
  # Dummy token: the mock accepts anything. A real deployment creates this Secret from a real token, typed by a person.
  k create secret generic lookout-gitlab-token --from-literal=token=lab-mock-token --dry-run=client -o yaml | k apply -f -
  k apply -f "$HERE/mock-gitlab.yaml"
  GL_URL="http://lookout-mock-gitlab.$NS.svc.cluster.local:8080"; GL_PROJECTS="lab/demo-app"; ROLL="deploy/lookout-mock-gitlab deploy/lookout-gitlab-mcp"
fi
sed -e "s#{{GITLAB_URL}}#$GL_URL#" -e "s#{{LOOKOUT_ALLOWED_PROJECTS}}#$GL_PROJECTS#" "$LOOKOUT/manifests/lookout-gitlab-mcp.yaml" | fix_api | k apply -f -
sed -e "s#{{MODEL_CONFIG}}#$MODEL_CONFIG#" -e "s#{{APPROVED_HARNESS}}#${HARNESS:-}#" "$AGENT_FILE" | k apply -f -
# ConfigMap edits do not restart pods: roll them so a re-deploy picks up code changes.
# shellcheck disable=SC2086
k rollout restart $ROLL >/dev/null
for d in $ROLL; do k rollout status "$d" --timeout=120s; done
for i in $(seq 1 45); do
  ready="$(k get "$AGENT_RES" mr-security-review -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
  [ "$ready" = "True" ] && { echo "agent mr-security-review READY"; exit 0; }
  sleep 4
done
echo "agent mr-security-review not Ready after 180s" >&2; k get "$AGENT_RES" mr-security-review -o yaml | tail -25 >&2; exit 1
