# Lifecycle Evaluation Review Manager

## TL;DR

Scores triage/remediation runs, enforces hard failures, and routes weak or
unsafe runs to review instead of allowing them to be treated as done.

## What This Feature Does

- Loads lifecycle eval cases.
- Scores one passing and one below-threshold run.
- Enforces hard gates such as mutation-before-HITL or missing verification.
- Routes failing cases to review-manager.
- Publishes metrics or reports where available.

## Evidence To Produce

- Eval cases loaded.
- Passing score.
- Below-threshold score.
- Hard gate output.
- Review-manager route.
- Metrics/report export or blocker.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/lifecycle-evaluation-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The eval path distinguishes good runs from weak or unsafe runs and routes
reviewable failures to the correct owner.
