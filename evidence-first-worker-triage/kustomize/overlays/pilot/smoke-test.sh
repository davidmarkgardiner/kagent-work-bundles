#!/usr/bin/env bash
set -euo pipefail
VALUES="${1:-values.env}"
[[ -f "$VALUES" ]] || { echo "Usage: $0 [values.env] [--cleanup]" >&2; exit 2; }
ACTION="${2:---apply}"
set -a; source "$VALUES"; set +a
if [[ "$ACTION" == "--cleanup" ]]; then
  kubectl -n "$WORKER_NAMESPACE" delete pod evidence-smoke-log evidence-smoke-oom evidence-smoke-unschedulable evidence-smoke-imagepull --ignore-not-found
  exit 0
fi
kubectl -n "$WORKER_NAMESPACE" apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata: {name: evidence-smoke-log, labels: {app.kubernetes.io/name: evidence-smoke-log}}
spec:
  restartPolicy: Never
  containers: [{name: app, image: busybox:1.36, command: [sh, -c, 'echo "ERROR unable to find ConfigMap demo-config token=not-a-real-token"; sleep 60']}]
---
apiVersion: v1
kind: Pod
metadata: {name: evidence-smoke-oom, labels: {app.kubernetes.io/name: evidence-smoke-oom}}
spec:
  restartPolicy: Never
  containers: [{name: app, image: busybox:1.36, resources: {limits: {memory: 32Mi}}, command: [sh, -c, 'head -c 96M /dev/zero >/dev/null']}]
---
apiVersion: v1
kind: Pod
metadata: {name: evidence-smoke-unschedulable, labels: {app.kubernetes.io/name: evidence-smoke-unschedulable}}
spec:
  nodeSelector: {evidence-first-never-scheduled: "true"}
  containers: [{name: app, image: busybox:1.36, command: [sh, -c, 'sleep 600']}]
---
apiVersion: v1
kind: Pod
metadata: {name: evidence-smoke-imagepull, labels: {app.kubernetes.io/name: evidence-smoke-imagepull}}
spec:
  containers: [{name: app, image: registry.invalid/evidence-first/not-found:never}]
EOF
echo 'Smoke fixtures applied. Wait 60 seconds, then run:'
echo '  ./verify-healthy.sh values.env'
echo "  kubectl -n $MANAGEMENT_NAMESPACE get workflows --sort-by=.metadata.creationTimestamp"
echo "  kubectl -n $MANAGEMENT_NAMESPACE logs -l eventsource-name=evidence-first-confluent --tail=100"
