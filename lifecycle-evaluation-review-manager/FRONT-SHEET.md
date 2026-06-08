# Lifecycle Evaluation Review Manager Work-Agent Bundle

Purpose: give a work agent a complete design/build/verification pack for
Kagent lifecycle evaluation, including offline eval, online eval, metric
contract, inline-vs-separate evaluator architecture, storage/access, audit
retention, and traceability.

## One-Line Ask

Implement or verify the lifecycle evaluation design in a work environment. Show
one passing and one below-threshold lifecycle evaluation, prove hard gates,
publish metrics or reports, define storage/access controls, and route the
failing case to review-manager.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `MEETING-ACTION-COVERAGE.md`
5. `ARCHITECTURE-DECISION.md`
6. `DATA-STORAGE-ACCESS-TRACEABILITY.md`
7. `requests/lifecycle-evaluation-request.yaml`
8. `prompts/01-run-lifecycle-eval.md`
9. `payload/REFERENCE.md`
10. `evidence/EVIDENCE-TEMPLATE.md`

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
OUTPUT_SANITIZED: yes
```
