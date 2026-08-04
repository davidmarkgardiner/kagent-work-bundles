#!/usr/bin/env bash
# Read-only verifier for the five-namespace smoke corpus. Confirms one open
# GitLab issue per expected pod and that each ticket meets the human-safety
# contract. It reads GitLab settings from Kubernetes, never prints the token,
# and NEVER creates, edits or deletes issues or cluster state.
#
# The v2 (home-replication) and v3 (specialist) paths write DIFFERENT ticket
# bodies and labels, so the verifier is path-aware. Both formats wrap the pod
# name in backticks, so matching keys on `<pod>`.
#
# Usage:
#   scripts/verify-smoke.sh --context <ctx> --path v2|v3 \
#     [--namespace argo-events] [--secret gitlab-credentials] \
#     [--label <label>] [--lenient]
#
# --path    v2 or v3 (REQUIRED). Selects the label default and the
#           human-approval boundary string to check.
# --label   GitLab label to filter on. Default: v3 -> aks-triage-smoke;
#           v2 -> none (v2 has no single smoke label, so all open issues are
#           scanned and matched by pod). Pass a label to narrow it.
# --lenient Downgrade the TL;DR / no-n/a / boundary checks to warnings; still
#           hard-fails on a missing ticket.
set -euo pipefail

CTX=""; NAMESPACE="argo-events"; SECRET="gitlab-credentials"
PATH_KIND=""; LABEL=""; LABEL_SET=0; LENIENT=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --context) CTX="$2"; shift 2 ;;
    --path) PATH_KIND="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --secret) SECRET="$2"; shift 2 ;;
    --label) LABEL="$2"; LABEL_SET=1; shift 2 ;;
    --lenient) LENIENT=1; shift ;;
    *) echo "usage: $0 --context <ctx> --path v2|v3 [--namespace argo-events] [--secret gitlab-credentials] [--label <label>] [--lenient]" >&2; exit 2 ;;
  esac
done
[ -n "$CTX" ] || { echo "--context is required" >&2; exit 2; }
case "$PATH_KIND" in
  v2) BOUNDARY="no change has been made"; DEFAULT_LABEL="" ;;
  v3) BOUNDARY="Plan only: human review"; DEFAULT_LABEL="aks-triage-smoke" ;;
  *) echo "--path must be v2 or v3" >&2; exit 2 ;;
esac
[ "$LABEL_SET" -eq 1 ] || LABEL="$DEFAULT_LABEL"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED="$ROOT/smoke/expected-outcomes.yaml"
[ -f "$EXPECTED" ] || { echo "cannot find $EXPECTED" >&2; exit 2; }

K=(kubectl --context "$CTX" -n "$NAMESPACE")
gitlab_url="$("${K[@]}" get secret "$SECRET" -o jsonpath='{.data.url}' | base64 -d)"
gitlab_token="$("${K[@]}" get secret "$SECRET" -o jsonpath='{.data.token}' | base64 -d)"
project_id="$("${K[@]}" get secret "$SECRET" -o jsonpath='{.data.project-id}' | base64 -d)"

# Only filter by label when one is set; v2 has no suite label so scan all open.
query=(--get --data-urlencode 'state=opened' --data-urlencode 'per_page=100')
[ -n "$LABEL" ] && query+=(--data-urlencode "labels=$LABEL")
issues="$(curl --fail --silent --show-error -H "PRIVATE-TOKEN: $gitlab_token" \
  "${query[@]}" "$gitlab_url/api/v4/projects/$project_id/issues")"

expected_pods="$(yq -r '.expected[].pod' "$EXPECTED")"
total=0; fail=0
soft() { if [ "$LENIENT" -eq 1 ]; then echo "WARN $*" >&2; else echo "FAIL $*" >&2; fail=1; fi; }

while IFS= read -r pod; do
  [ -n "$pod" ] || continue
  total=$((total+1))
  # Both paths wrap the pod in backticks; match on `<pod>`.
  issue="$(jq -c --arg pod "$pod" '[.[] | select(.description | contains("`" + $pod + "`"))] | first // empty' <<<"$issues")"
  if [ -z "$issue" ]; then
    echo "FAIL missing ticket for $pod" >&2; fail=1; continue
  fi
  description="$(jq -r '.description' <<<"$issue")"
  if ! printf '%s\n' "$description" | awk 'NF {print; exit}' | grep -Fx '## TL;DR' >/dev/null; then
    soft "$pod: ticket does not start with ## TL;DR"
  fi
  if printf '%s\n' "$description" | grep -Eiq '(^|[^[:alnum:]])n/?a([^[:alnum:]]|$)'; then
    soft "$pod: ticket contains forbidden n/a placeholder"
  fi
  if ! printf '%s\n' "$description" | grep -Fq "$BOUNDARY"; then
    soft "$pod: ticket does not preserve the human approval boundary (expected '$BOUNDARY')"
  fi
  echo "PASS $pod: $(jq -r '.web_url' <<<"$issue")"
done <<<"$expected_pods"

echo "----"
echo "path: $PATH_KIND    expected tickets: $total    label: ${LABEL:-<none>}"
[ "$fail" -eq 0 ] || { echo "FIVE_NAMESPACE_SMOKE_EVALUATION: failed" >&2; exit 1; }
echo "FIVE_NAMESPACE_SMOKE_EVALUATION: passed ($total/$total)"
