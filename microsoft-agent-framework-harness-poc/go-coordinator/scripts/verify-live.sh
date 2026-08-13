#!/usr/bin/env sh
set -eu
ctx=${1:-red}
for name in maf-go-issue-summariser maf-go-sre-triage maf-go-uk8s-healthcheck; do
  kubectl --context "$ctx" -n kagent get agent "$name" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' | grep -qx True
done
printf '%s\n' GO_HARNESS_SPECIALISTS_READY_OK
printf '%s\n' GO_HARNESS_LIVE_EVIDENCE_REVIEW_REQUIRED
