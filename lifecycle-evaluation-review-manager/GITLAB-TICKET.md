# GitLab Ticket: Prove Lifecycle Evaluation And Review Routing

## Summary

Prove Kagent triage/remediation runs are scored and below-threshold or unsafe
runs are routed to review-manager.

## Feature

The lifecycle evaluation workflow should score passing and failing cases,
enforce hard gates, publish evidence, and create a review route for weak runs.

## Evidence Required

- Eval case names.
- Passing run score.
- Below-threshold run score.
- Hard failure markers.
- Review-manager route.
- Metrics/report output or blocker.

## Acceptance Criteria

- `EVAL_CASES_LOADED: yes`
- `PASSING_RUN_SCORED: yes`
- `BELOW_THRESHOLD_RUN_SCORED: yes`
- `HARD_FAILURES_ENFORCED: yes`
- `REVIEW_MANAGER_ROUTED: yes`
- `METRICS_EXPORTED: yes_or_blocked`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not infer evaluation health from one metric. Include recent failed workflow
cases where they exist.
