#!/usr/bin/env bash
# Fire disposable fixtures and prove the path end to end: pod log + Kubernetes
# event -> Vector -> Kafka -> Argo -> agent -> GitLab.
#
#   bash scripts/smoke-test.sh --context <kubectl-context> [--keep]
#
# Creates pods ONLY in the proof namespace and deletes them at the end unless
# --keep. It does create real GitLab work items — that is the point of the test.
# Close them afterwards; the fingerprint labels make them easy to find:
#   labels=automated-triage
set -uo pipefail

CONTEXT=""; KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --context) CONTEXT="${2:?--context needs a value}"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$CONTEXT" ] || { echo "ERROR: --context is required" >&2; exit 2; }
K="kubectl --context $CONTEXT"
NS=agentic-triage-proof
HERE="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%H%M%S)"

echo "== Baseline =="
before_wf="$($K -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage --no-headers 2>/dev/null | wc -l | tr -d ' ')"
echo "  triage workflows before: $before_wf"

echo
echo "== Fire fixtures into $NS =="
# 1. Log path: a pod that prints an ERROR line containing a fake credential, so
#    the same run also proves redaction.
# 2. Event path: a crashlooping pod, which produces BackOff Warning events.
$K apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: smoke-log-$STAMP
  namespace: $NS
  labels: {app.kubernetes.io/name: smoke-log, triage-smoke: "true"}
spec:
  restartPolicy: Never
  containers:
    - name: smoke-log
      image: busybox:1.36
      command: [sh, -c]
      args: ['echo "ERROR smoke-test $STAMP upstream authorization timeout password=must-be-redacted"; sleep 180']
      resources: {requests: {cpu: 10m, memory: 16Mi}, limits: {cpu: 50m, memory: 32Mi}}
---
apiVersion: v1
kind: Pod
metadata:
  name: smoke-crashloop-$STAMP
  namespace: $NS
  labels: {app.kubernetes.io/name: smoke-crashloop, triage-smoke: "true"}
spec:
  restartPolicy: Always
  containers:
    - name: smoke-crashloop
      image: busybox:1.36
      command: [sh, -c]
      args: ['echo "FATAL smoke-test $STAMP unrecoverable startup failure"; exit 1']
      resources: {requests: {cpu: 10m, memory: 16Mi}, limits: {cpu: 50m, memory: 32Mi}}
EOF

echo
echo "== Wait for workflows (up to 6 min) =="
deadline=$(( $(date +%s) + 360 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  now_wf="$($K -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  running="$($K -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage -o jsonpath='{.items[*].status.phase}' 2>/dev/null | tr ' ' '\n' | grep -c Running)"
  if [ "$now_wf" -gt "$before_wf" ] && [ "$running" -eq 0 ]; then break; fi
  sleep 15
done

echo
echo "== Workflows =="
$K -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage

echo
echo "== Ticket outcomes =="
for p in $($K -n argo-events get pods -o name 2>/dev/null | grep -E 'create-gitlab-issue|append-correlated'); do
  line="$($K -n argo-events logs "$p" -c main 2>/dev/null | grep -iE 'issue (created|appended)|Reused existing|Correlated evidence' | head -1)"
  [ -n "$line" ] && echo "  ${p##*/}: $line"
done

echo
echo "== Dedupe claims =="
for c in $($K -n argo-events get cm -o name 2>/dev/null | grep triage-dedupe); do
  echo "  ${c##*/}: $($K -n argo-events get "$c" -o jsonpath='{.data.state}') iid=$($K -n argo-events get "$c" -o jsonpath='{.data.issue_iid}')"
done

echo
echo "== Quarantined (DLQ) =="
$K -n argo-events get cm -l triage-quarantine=true --no-headers 2>/dev/null || echo "  none"

echo
echo "== What to check by hand =="
cat <<'TXT'
  1. Open each new GitLab work item. It must carry: severity header, fingerprint,
     cluster/namespace/node/pod/container, the reach-back kubectl block, and a
     non-empty "Read-only kagent triage" section.
  2. Grep the ticket body for the fixture's fake credential. It MUST appear as
     [REDACTED] and never in clear text.
  3. If any ticket carries the label `triage-agent-unavailable`, the agent
     backend was down/erroring for that ticket — the evidence is still good but
     the analysis is missing. Investigate the agent, not the pipeline.
  4. Two signals for the SAME pod (the log line and the crashloop event) must
     produce ONE ticket plus an appended note, never two tickets.
TXT

if [ "$KEEP" -eq 0 ]; then
  echo
  echo "== Cleanup =="
  $K -n "$NS" delete pod -l triage-smoke=true --wait=false
else
  echo
  echo "Fixtures kept (--keep). Remove with: $K -n $NS delete pod -l triage-smoke=true"
fi
