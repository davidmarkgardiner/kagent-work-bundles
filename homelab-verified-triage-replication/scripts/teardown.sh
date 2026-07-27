#!/usr/bin/env bash
# Remove everything this bundle created. Touches nothing else.
#
#   bash scripts/teardown.sh --context <ctx> [--keep-claims] [--keep-dlq]
#
# It does NOT delete: the Secrets, the ServiceAccounts, the EventBus, the kagent
# agent, the argo-events/monitoring/kagent namespaces, or any GitLab issue.
# Close tickets yourself — they carry the `automated-triage` label.
set -uo pipefail

CONTEXT=""; KEEP_CLAIMS=0; KEEP_DLQ=0
while [ $# -gt 0 ]; do
  case "$1" in
    --context) CONTEXT="${2:?--context needs a value}"; shift 2 ;;
    --keep-claims) KEEP_CLAIMS=1; shift ;;
    --keep-dlq) KEEP_DLQ=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$CONTEXT" ] || { echo "ERROR: --context is required" >&2; exit 2; }
K="kubectl --context $CONTEXT"

echo "Tearing down the triage path on context: $CONTEXT"
echo "The following will be deleted:"
echo "  argo-events: eventsource/red-telemetry-triage-kafka, sensors red-log-triage + red-event-triage,"
echo "               workflowtemplate/red-agentic-triage, cm/triage-workflow-concurrency,"
echo "               deploy+svc+cm vector-telemetry-triage, all triage workflows"
echo "  monitoring:  deploy+cm alloy-vector-triage"
echo "  namespace:   agentic-triage-proof (and every pod in it)"
[ "$KEEP_CLAIMS" -eq 0 ] && echo "  argo-events: all triage-dedupe-* claim ConfigMaps"
[ "$KEEP_DLQ" -eq 0 ]    && echo "  argo-events: all quarantined (DLQ) ConfigMaps"
printf 'Continue? [y/N] '
read -r ans
case "$ans" in y|Y|yes|YES) : ;; *) echo "Aborted."; exit 1 ;; esac

echo
echo "== Management backend =="
$K -n argo-events delete workflow -l app.kubernetes.io/part-of=alloy-vector-kafka-triage --ignore-not-found
$K -n argo-events delete sensor red-log-triage red-event-triage --ignore-not-found
$K -n argo-events delete eventsource red-telemetry-triage-kafka --ignore-not-found
$K -n argo-events delete workflowtemplate red-agentic-triage --ignore-not-found
$K -n argo-events delete cm triage-workflow-concurrency --ignore-not-found

echo
echo "== Worker Vector =="
$K -n argo-events delete deploy vector-telemetry-triage --ignore-not-found
$K -n argo-events delete svc vector-telemetry-triage --ignore-not-found
$K -n argo-events delete cm vector-telemetry-triage-red-config --ignore-not-found

echo
echo "== Worker Alloy =="
$K -n monitoring delete deploy alloy-vector-triage --ignore-not-found
$K -n monitoring delete cm alloy-vector-triage-red-config --ignore-not-found

if [ "$KEEP_CLAIMS" -eq 0 ]; then
  echo
  echo "== Dedupe claims =="
  names="$($K -n argo-events get cm -o name 2>/dev/null | grep triage-dedupe || true)"
  if [ -n "$names" ]; then printf '%s\n' "$names" | xargs -r $K -n argo-events delete; else echo "  none"; fi
fi

if [ "$KEEP_DLQ" -eq 0 ]; then
  echo
  echo "== Quarantined (DLQ) records =="
  $K -n argo-events delete cm -l triage-quarantine=true --ignore-not-found
fi

echo
echo "== Proof namespace =="
$K delete ns agentic-triage-proof --ignore-not-found

echo
echo "Done. Left in place (not created by this bundle): Secrets, ServiceAccounts,"
echo "EventBus, kagent agent, and the argo-events / monitoring / kagent namespaces."
echo "GitLab issues are untouched — close them via label \`automated-triage\`."
