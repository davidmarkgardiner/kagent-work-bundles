#!/usr/bin/env sh
set -eu
ctx=${1:-red}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
coordinator_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
(
  cd "$coordinator_dir"
  go test .
)
printf '%s\n' GO_HARNESS_LOCAL_EVALUATION_TESTS_OK
for name in maf-go-issue-summariser maf-go-sre-triage maf-go-uk8s-healthcheck; do
  kubectl --context "$ctx" -n kagent get agent "$name" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' | grep -qx True
done
printf '%s\n' GO_HARNESS_SPECIALISTS_READY_OK
printf '%s\n' GO_HARNESS_LIVE_EVIDENCE_REVIEW_REQUIRED
