# Lifecycle Evaluation Review Manager Work-Agent Bundle

Purpose: prove Kagent triage/remediation runs are scored, hard failures are
enforced, and weak runs are routed to review instead of being treated as done.

## One-Line Ask

Run one passing and one below-threshold lifecycle evaluation, show hard gates,
publish metrics or reports, and route the failing case to review-manager.

## Required Markers

```text
EVAL_CASES_LOADED: yes
PASSING_RUN_SCORED: yes
BELOW_THRESHOLD_RUN_SCORED: yes
HARD_FAILURES_ENFORCED: yes
REVIEW_MANAGER_ROUTED: yes
METRICS_EXPORTED: yes_or_blocked
OUTPUT_SANITIZED: yes
```
