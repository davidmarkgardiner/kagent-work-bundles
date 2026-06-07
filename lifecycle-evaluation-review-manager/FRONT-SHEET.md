# Lifecycle Evaluation Review Manager Work-Agent Bundle

Purpose: prove Kagent triage/remediation runs are scored, hard failures are
enforced, and weak runs are routed to review instead of being treated as done.

## One-Line Ask

Run one passing and one below-threshold lifecycle evaluation, show hard gates,
publish metrics or reports, and route the failing case to review-manager.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/lifecycle-evaluation-request.yaml`
5. `prompts/01-run-lifecycle-eval.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live eval cases, scorer, metrics export, review-manager, or kagent
behavior.

## Live Audit Rule

Do not infer evaluation health from a single metric or one successful workflow.
Inspect recent eval and chaos/eval-related workflow runs, report failed
historical cases, and distinguish "metric exists" from "latest lifecycle eval
completed and enforced gates".

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
