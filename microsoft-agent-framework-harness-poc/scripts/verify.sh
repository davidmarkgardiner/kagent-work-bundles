#!/usr/bin/env sh
set -eu

context="${1:-red}"
ns=kagent

kubectl --context "$context" -n "$ns" get agent debt-a2a-prd -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' | grep -qx True
kubectl --context "$context" -n "$ns" wait --for=condition=complete job/maf-harness-request --timeout=60s
kubectl --context "$context" -n "$ns" logs job/maf-harness-request | grep -q 'HARNESS_REQUEST_RECORDED status=awaiting-approval tool_invoked=false'
kubectl --context "$context" -n "$ns" wait --for=condition=complete job/maf-harness-approve --timeout=300s
kubectl --context "$context" -n "$ns" logs job/maf-harness-approve | grep -q 'HARNESS_APPROVAL_COMPLETED tool_invoked=True'
printf '%s\n' 'MAF_HARNESS_KAGENT_POC_VERIFY_PASS'
