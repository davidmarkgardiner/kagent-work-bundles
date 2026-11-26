#!/usr/bin/env bash
# Filter: manifests on stdin, same manifests on stdout, with Istio injection off on every
# pod template and limits added to the postgres tls-reloader. Needs kubectl.
# Used as the Helm 3 post-renderer and for the postgres manifest (POLICY_FILTER).
set -euo pipefail
d="$(mktemp -d)"; trap 'rm -rf "$d"' EXIT
cat > "$d/all.yaml"
{
  printf 'resources: [all.yaml]\npatches:\n'
  for kv in apps/v1:Deployment apps/v1:DaemonSet apps/v1:StatefulSet batch/v1:Job; do
    printf -- '- target: {kind: %s}\n  patch: |-\n' "${kv#*:}"
    printf '    apiVersion: %s\n    kind: %s\n    metadata: {name: any}\n' "${kv%:*}" "${kv#*:}"
    printf '    spec: {template: {metadata: {labels: {istio-injection: disabled, sidecar.istio.io/inject: "false"}}}}\n'
  done
  if grep -q 'name: tls-reloader' "$d/all.yaml"; then
    printf -- '- target: {kind: StatefulSet, name: postgres}\n  patch: |-\n'
    printf '    apiVersion: apps/v1\n    kind: StatefulSet\n    metadata: {name: postgres}\n'
    printf '    spec: {template: {spec: {initContainers: [{name: tls-reloader, resources: {limits: {cpu: 100m, memory: 64Mi}}}]}}}\n'
  fi
} > "$d/kustomization.yaml"
kubectl kustomize "$d"
