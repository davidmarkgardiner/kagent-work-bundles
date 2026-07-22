#!/usr/bin/env bash
# Delete the isolated substrate kind cluster and reclaim resources.
set -uo pipefail
CLUSTER="${CLUSTER:-kagent-substrate}"
echo "Deleting kind cluster ${CLUSTER} ..."
kind delete cluster --name "${CLUSTER}"
echo "Done. To only remove substrate/kagent but keep the cluster, instead run:"
echo "  helm --kube-context kind-${CLUSTER} uninstall kagent kagent-crds -n kagent"
echo "  helm --kube-context kind-${CLUSTER} uninstall substrate substrate-crds -n ate-system"
