# Lifecycle Evaluation Review Manager Work-Agent Bundle

Purpose: give a work agent a complete design/build/verification pack for
Kagent lifecycle evaluation, including offline eval, online eval, metric
contract, inline-vs-separate evaluator architecture, storage/access, audit
retention, traceability, and the phase-1 chaos-event-to-evaluation proof loop.

## One-Line Ask

Implement or verify the lifecycle evaluation design in a work environment. Show
one passing and one below-threshold lifecycle evaluation, prove hard gates,
publish metrics or reports, define storage/access controls, and produce a
review-manager route payload for failing cases. Then prove or block the
end-to-end flow from chaos event to Kagent triage, lifecycle evaluation, and
GitLab evidence. Grafana alert triggering is optional for phase 1; an Argo
EventSource, Litmus ChaosResult event, Kubernetes event watcher, or Argo
workflow watch is sufficient.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `MEETING-ACTION-COVERAGE.md`
5. `ARCHITECTURE-DECISION.md`
6. `DATA-STORAGE-ACCESS-TRACEABILITY.md`
7. `requests/lifecycle-evaluation-request.yaml`
8. `prompts/01-run-lifecycle-eval.md`
9. `prompts/02-prove-chaos-event-to-eval-gitlab.md`
10. `CHAOS-TO-EVAL-FLOW.md`
11. `payload/REFERENCE.md`
12. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live eval cases, scorer, metrics export, review-manager payloads, or kagent
behavior.

## Live Audit Rule

Do not infer evaluation health from a single metric or one successful workflow.
Inspect recent eval and chaos/eval-related workflow runs, report failed
historical cases, and distinguish "metric exists" from "latest lifecycle eval
completed and enforced gates".

## Required Markers

```text
WORK_VARIABLES_RESOLVED: yes
EVALUATION_FRAMEWORK_DESIGN: covered
OFFLINE_ONLINE_DESIGN: covered
KEY_METRICS_IDENTIFIED: covered
INLINE_VS_SEPARATE_ARCHITECTURE: covered
DATA_STORAGE_ACCESS_MODEL: covered
AUDIT_RETENTION_TRACEABILITY: covered
EVAL_CASES_LOADED: yes
PASSING_RUN_SCORED: yes
BELOW_THRESHOLD_RUN_SCORED: yes
HARD_FAILURES_ENFORCED: yes
REVIEW_MANAGER_ROUTED: yes
METRICS_EXPORTED: yes_or_blocked
CHAOS_EVENT_FLOW_MAPPED: yes
ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked
CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked
GITLAB_EVIDENCE_UPDATED: yes_or_blocked
GRAFANA_ALERT_TRIGGER: not_required_for_phase_1
OUTPUT_SANITIZED: yes
```
