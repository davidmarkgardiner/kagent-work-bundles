#!/usr/bin/env sh
set -eu

context="${1:-red}"
ns=kagent

for agent_name in maf-sdlc-plan maf-sdlc-build maf-sdlc-test maf-sdlc-document maf-sdlc-evaluator; do
  kubectl --context "$context" -n "$ns" get "agent/$agent_name" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' | grep -qx True
done
kubectl --context "$context" -n "$ns" wait --for=condition=complete job/maf-harness-sdlc-factory --timeout=600s
kubectl --context "$context" -n "$ns" logs job/maf-harness-sdlc-factory | grep -q 'HARNESS_SDLC_FACTORY_COMPLETED stages=plan,build,test,document,evaluate'
printf '%s\n' 'MAF_HARNESS_SDLC_FACTORY_VERIFY_PASS'
