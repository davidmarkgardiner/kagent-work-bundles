# GitLab Ticket: Prove Lifecycle Evaluation And Review Routing

## Summary

Design and prove Kagent lifecycle evaluation for triage/remediation workflows,
including offline eval, online eval, key metrics, evaluator architecture,
storage/access, audit retention, traceability, and review-manager routing.

## Feature

The lifecycle evaluation workflow should score passing and failing cases,
enforce hard gates, publish evidence, and create a review route for weak runs.
The design must cover the planning-meeting evaluation actions.

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
- `OUTPUT_SANITIZED: yes`

## Notes

Do not infer evaluation health from one metric. Include recent failed workflow
cases where they exist.
