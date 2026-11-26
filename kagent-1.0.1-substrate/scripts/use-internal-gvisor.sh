#!/usr/bin/env bash
# Points SandboxConfig/gvisor-default at the copies in RustFS.
# MUTATES the current cluster. A Helm upgrade of `substrate` can revert it: re-run
# after upgrades, or carry the same rewrite as a post-renderer in GitOps.
set -euo pipefail
kubectl get sandboxconfig gvisor-default -o yaml \
  | sed 's#gs://gvisor/releases/release/#s3://ate-snapshots/gvisor/#g' \
  | kubectl apply -f -
kubectl get sandboxconfig gvisor-default -o yaml | grep -n 'url:'
