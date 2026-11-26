#!/usr/bin/env bash
# LAB/TEST ONLY. Deploys Lookout config review against the MOCK GitLab (project lab/platform-config, MRs 21-23).
# The lab cluster plays both "real cluster" (read-only reads) and "sandbox" (lookout-mr-* namespaces). At work these are
# two clusters: see CONFIG-REVIEW-DESIGN.md. Needs deploy-lab.sh to have run once (mock GitLab + token Secret).
#   KUBE_CONTEXT=kind-kagent-alpha17 HARNESS=aks-docs-v1 MODEL_CONFIG=glm-coding ./deploy-config-review.sh   # kagent 1.x
#   KUBE_CONTEXT=<ctx> KAGENT_API=0.9 MODEL_CONFIG=<mc> ./deploy-config-review.sh                             # kagent 0.7.x / 0.9
#   KUBE_CONTEXT=kind-kagent-alpha17 ./deploy-config-review.sh down
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LOOKOUT="$(dirname "$HERE")"
CTX="${KUBE_CONTEXT:?set KUBE_CONTEXT to the lab context (never a work or production context)}"
NS=kagent
k() { kubectl --context "$CTX" "$@"; }

if [ "${1:-}" = "down" ]; then
  for r in agents.api.kagent.dev agents.kagent.dev; do k -n "$NS" delete "$r" mr-config-review --ignore-not-found 2>/dev/null || true; done
  for r in remotemcpservers.api.kagent.dev remotemcpservers.kagent.dev; do k -n "$NS" delete "$r" lookout-config-review-mcp --ignore-not-found 2>/dev/null || true; done
  k -n "$NS" delete deploy,svc lookout-config-review-mcp --ignore-not-found
  k -n "$NS" delete cronjob lookout-config-review-janitor --ignore-not-found
  k -n "$NS" delete configmap lookout-config-review-mcp --ignore-not-found
  k delete validatingadmissionpolicybinding,validatingadmissionpolicy lookout-config-review-scope lookout-kro-children-scope --ignore-not-found
  k delete clusterrolebinding,clusterrole lookout-config-review --ignore-not-found
  k -n "$NS" delete sa lookout-config-review --ignore-not-found
  k get ns -l lookout.dev/sandbox=true -o name | xargs -r kubectl --context "$CTX" delete --wait=false
  echo "config review lab objects removed"; exit 0
fi

MODEL_CONFIG="${MODEL_CONFIG:?set MODEL_CONFIG}"
API="${KAGENT_API:-1x}"
if [ "$API" = "1x" ]; then
  HARNESS="${HARNESS:?set HARNESS (kagent 1.x)}"; AGENT_RES=agents.api.kagent.dev
  AGENT_FILE="$LOOKOUT/manifests/mr-config-review-agent-v1alpha3.yaml"
  fix_api() { sed -e 's#apiVersion: kagent.dev/v1alpha2#apiVersion: api.kagent.dev/v1alpha3#'; }
else
  HARNESS=""; AGENT_RES=agents.kagent.dev
  AGENT_FILE="$LOOKOUT/manifests/mr-config-review-agent.yaml"
  fix_api() { cat; }
fi
k -n "$NS" get secret lookout-gitlab-token >/dev/null || { echo "run deploy-lab.sh first (mock GitLab + token Secret)" >&2; exit 1; }
# The mock serves lab/platform-config from this fixture file next to its server.py.
k -n "$NS" create configmap lookout-mock-gitlab --from-file=server.py="$HERE/mock_gitlab.py" \
  --from-file=platform-config-mrs.json="$LOOKOUT/config_review/fixtures/platform-config-mrs.json" --dry-run=client -o yaml | k -n "$NS" apply -f -
k -n "$NS" create configmap lookout-config-review-mcp \
  --from-file=config_review_mcp.py="$LOOKOUT/config_review_mcp.py" --from-file=gitlab_review_mcp.py="$LOOKOUT/gitlab_review_mcp.py" \
  --from-file=init.py="$LOOKOUT/config_review/__init__.py" --from-file=engine.py="$LOOKOUT/config_review/engine.py" \
  --from-file=kube.py="$LOOKOUT/config_review/kube.py" --from-file=sandbox.py="$LOOKOUT/config_review/sandbox.py" \
  --from-file=janitor.py="$LOOKOUT/config_review/janitor.py" \
  --dry-run=client -o yaml | k -n "$NS" apply -f -
# kro instance kinds the sandbox may create: the real plural (from its CRD) of every live RGD's kind.
KINDS="$(k get rgd -o jsonpath='{range .items[*]}{.spec.schema.kind}{"\n"}{end}' | sort -u)"
PLURALS="$(k get crd -o jsonpath='{range .items[*]}{.spec.names.kind} {.spec.names.plural}{"\n"}{end}' \
  | awk 'NR==FNR{want[$1]=1;next} ($1 in want){print $2}' <(printf '%s\n' "$KINDS") - | sort -u | paste -sd, -)"
sed -e "s#{{GITLAB_URL}}#http://lookout-mock-gitlab.$NS.svc.cluster.local:8080#" -e "s#{{LOOKOUT_ALLOWED_PROJECTS}}#lab/platform-config#" \
    -e "s#{{INSTANCE_PLURALS}}#${PLURALS:-none}#" -e "s#{{PYPI_INDEX}}##" \
    "$LOOKOUT/manifests/config-review-sandbox.yaml" | fix_api | k apply -f -
sed -e "s#{{MODEL_CONFIG}}#$MODEL_CONFIG#" -e "s#{{APPROVED_HARNESS}}#$HARNESS#" "$AGENT_FILE" | k apply -f -
k -n "$NS" rollout restart deploy/lookout-mock-gitlab deploy/lookout-config-review-mcp >/dev/null
k -n "$NS" rollout status deploy/lookout-mock-gitlab --timeout=120s
k -n "$NS" rollout status deploy/lookout-config-review-mcp --timeout=180s
for i in $(seq 1 45); do
  ready="$(k -n "$NS" get "$AGENT_RES" mr-config-review -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
  [ "$ready" = "True" ] && { echo "agent mr-config-review READY"; exit 0; }
  sleep 4
done
echo "agent mr-config-review not Ready after 180s" >&2; exit 1
