#!/usr/bin/env bash
set -euo pipefail
bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
eval_root="${bundle_root}/payload/agent-evals"
cd "${bundle_root}"
for rel in \
  FRONT-SHEET.md \
  WORK-AGENT-START-PROMPT.md \
  CHECKLIST.md \
  MEETING-ACTION-COVERAGE.md \
  ARCHITECTURE-DECISION.md \
  DATA-STORAGE-ACCESS-TRACEABILITY.md \
  IMPLEMENTATION-VERIFY-PLAN.md \
  CHAOS-TO-EVAL-FLOW.md \
  HOMELAB-VERIFICATION-EVIDENCE.md \
  requests/lifecycle-evaluation-request.yaml \
  prompts/01-run-lifecycle-eval.md \
  prompts/02-prove-chaos-event-to-eval-gitlab.md \
  payload/REFERENCE.md \
  payload/agent-evals/scripts/reporting.py \
  payload/agent-evals/scripts/metrics.py \
  payload/agent-evals/scripts/collect-lifecycle-evidence.py \
  payload/agent-evals/scripts/score-lifecycle-run.py \
  payload/agent-evals/scripts/summarize-agent-scores.py \
  payload/agent-evals/scripts/route-lifecycle-review.py \
  payload/agent-evals/lifecycle-cases/pod-crashloop-hitl-remediation.yaml \
  payload/agent-evals/lifecycle-cases/chaos-pod-delete.yaml \
  payload/agent-evals/results/sample/lifecycle/pod-crashloop-hitl-remediation.lifecycle-run.json \
  payload/agent-evals/results/sample/lifecycle/chaos-pod-delete-below-threshold.lifecycle-run.json \
  evidence/EVIDENCE-TEMPLATE.md; do
  [[ -f "${rel}" ]] || { echo "MISSING ${rel}" >&2; exit 1; }
  echo "FOUND ${rel}"
done
for marker in \
  "WORK_VARIABLES_RESOLVED: yes" \
  "EVALUATION_FRAMEWORK_DESIGN: covered" \
  "OFFLINE_ONLINE_DESIGN: covered" \
  "KEY_METRICS_IDENTIFIED: covered" \
  "INLINE_VS_SEPARATE_ARCHITECTURE: covered" \
  "DATA_STORAGE_ACCESS_MODEL: covered" \
  "AUDIT_RETENTION_TRACEABILITY: covered" \
  "EVAL_CASES_LOADED: yes" \
  "PASSING_RUN_SCORED: yes" \
  "BELOW_THRESHOLD_RUN_SCORED: yes" \
  "HARD_FAILURES_ENFORCED: yes" \
  "REVIEW_MANAGER_ROUTED: yes" \
  "METRICS_EXPORTED: yes_or_blocked" \
  "CHAOS_EVENT_FLOW_MAPPED: yes" \
  "ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked" \
  "CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked" \
  "GITLAB_EVIDENCE_UPDATED: yes_or_blocked" \
  "GRAFANA_ALERT_TRIGGER: not_required_for_phase_1" \
  "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "${marker}" . || { echo "MARKER_MISSING ${marker}" >&2; exit 1; }
  echo "MARKER_OK ${marker}"
done

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

PYTHONPATH="${eval_root}/scripts" python3 "${eval_root}/scripts/score-lifecycle-run.py" \
  --case "${eval_root}/lifecycle-cases/pod-crashloop-hitl-remediation.yaml" \
  --run "${eval_root}/results/sample/lifecycle/pod-crashloop-hitl-remediation.lifecycle-run.json" \
  --output-dir "${tmp_dir}/pass"
echo "PASSING_RUN_SCORED: yes"

if PYTHONPATH="${eval_root}/scripts" python3 "${eval_root}/scripts/score-lifecycle-run.py" \
  --case "${eval_root}/lifecycle-cases/chaos-pod-delete.yaml" \
  --run "${eval_root}/results/sample/lifecycle/chaos-pod-delete-below-threshold.lifecycle-run.json" \
  --output-dir "${tmp_dir}/fail"; then
  echo "BELOW_THRESHOLD_RUN_UNEXPECTEDLY_PASSED" >&2
  exit 1
else
  echo "BELOW_THRESHOLD_RUN_SCORED: yes"
  echo "HARD_FAILURES_ENFORCED: yes"
fi

PYTHONPATH="${eval_root}/scripts" python3 "${eval_root}/scripts/route-lifecycle-review.py" \
  --results-dir "${tmp_dir}/fail" \
  --output "${tmp_dir}/review-route.json"
rg -q '"review_manager_route": "review-manager"' "${tmp_dir}/review-route.json"
echo "REVIEW_MANAGER_ROUTED: yes"

PYTHONPATH="${eval_root}/scripts" python3 "${eval_root}/scripts/summarize-agent-scores.py" \
  --results-dir "${tmp_dir}" \
  --summary-md "${tmp_dir}/summary.md" \
  --metrics "${tmp_dir}/agent-eval.prom"
rg -q "agent_lifecycle_eval_score|agent_lifecycle_eval_hard_failures|agent_lifecycle_eval_subscore" "${tmp_dir}/agent-eval.prom"
echo "METRICS_EXPORTED: yes"

echo "LIFECYCLE_EVALUATION_REVIEW_MANAGER_BUNDLE_VERIFY: passed"
