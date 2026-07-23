#!/usr/bin/env bash
# Delete the isolated kind cluster and reclaim resources.
set -uo pipefail
CLUSTER="${CLUSTER:-kagent-memory}"
kind delete cluster --name "$CLUSTER"
echo "deleted kind cluster: $CLUSTER"
