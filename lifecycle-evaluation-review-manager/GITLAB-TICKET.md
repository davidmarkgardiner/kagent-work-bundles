# GitLab Ticket: Prove Lifecycle Evaluation And Review Routing

## Summary

Design and prove Kagent lifecycle evaluation for triage/remediation workflows,
including offline eval, online eval, key metrics, evaluator architecture,
storage/access, audit retention, traceability, review-manager routing, and the
phase-1 chaos-event-to-triage-to-evaluation evidence loop.

## Feature

The lifecycle evaluation workflow should score passing and failing cases,
enforce hard gates, publish evidence, and create a review route for weak runs.
The design must cover the planning-meeting evaluation actions. It should also
prove or explicitly block a chaos-tested action flowing from Argo
Events/Litmus/Kubernetes event observation into Kagent triage, lifecycle
evaluation, and GitLab documentation. Grafana alert triggering is optional for
this phase.

## Evidence Required

- Eval case names.
- Evaluation framework design link.
- Offline and online evaluation design summary.
- Key evaluation metric names and labels.
- Inline versus separate evaluator architecture decision.
- Data storage and access-control model.
- Audit retention and traceability model.
- Passing run score.
- Below-threshold run score.
- Hard failure markers.
- Review-manager route.
- Chaos event source or watcher proof.
- Triage run ID and input payload.
- Lifecycle eval result for the chaos-tested action.
- GitLab issue, MR, comment, or report URL.
- Metrics/report output or blocker.

## Acceptance Criteria

- `EVAL_CASES_LOADED: yes`
- `EVALUATION_FRAMEWORK_DESIGN: covered`
- `OFFLINE_ONLINE_DESIGN: covered`
- `KEY_METRICS_IDENTIFIED: covered`
- `INLINE_VS_SEPARATE_ARCHITECTURE: covered`
- `DATA_STORAGE_ACCESS_MODEL: covered`
- `AUDIT_RETENTION_TRACEABILITY: covered`
- `PASSING_RUN_SCORED: yes`
- `BELOW_THRESHOLD_RUN_SCORED: yes`
- `HARD_FAILURES_ENFORCED: yes`
- `REVIEW_MANAGER_ROUTED: yes`
- `METRICS_EXPORTED: yes_or_blocked`
- `CHAOS_EVENT_FLOW_MAPPED: yes`
- `ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked`
- `CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked`
- `GITLAB_EVIDENCE_UPDATED: yes_or_blocked`
- `GRAFANA_ALERT_TRIGGER: not_required_for_phase_1`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not infer evaluation health from one metric. Include recent failed workflow
cases where they exist.
