# Lifecycle Evaluation Review Manager

## TL;DR

Design, build, and verify lifecycle evaluation for Kagent triage/remediation
runs. The bundle covers offline eval, online eval, key metrics, inline versus
separate evaluator architecture, storage/access, audit retention, and
traceability.

## What This Feature Does

- Maps the Microsoft meeting actions to repo design docs.
- Loads lifecycle eval cases and scorer.
- Scores one passing and one below-threshold run.
- Enforces hard gates such as mutation-before-HITL or missing verification.
- Verifies the online Argo evaluator architecture.
- Confirms the independent metrics library and label policy.
- Defines storage, access, retention, and traceability evidence.
- Routes failing cases to review-manager.

## Evidence To Produce

- Meeting action coverage.
- Offline evaluation design summary.
- Online evaluation design summary.
- Key metric names and labels.
- Inline versus separate evaluator architecture decision.
- Data storage and access-control model.
- Audit retention and traceability model.
- Passing score and below-threshold score.
- Hard gate output.
- Review-manager route.
- Metrics/report export or blocker.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/lifecycle-evaluation-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## File Map

| File | Purpose |
| --- | --- |
| `MEETING-ACTION-COVERAGE.md` | Maps each Microsoft meeting action to design docs and required evidence. |
| `ARCHITECTURE-DECISION.md` | Explains inline versus separate evaluator and the selected hybrid pattern. |
| `DATA-STORAGE-ACCESS-TRACEABILITY.md` | Defines storage classes, RBAC boundaries, retention, and traceability fields. |
| `IMPLEMENTATION-VERIFY-PLAN.md` | Step-by-step build and verification plan for a work environment. |
| `WORK-AGENT-START-PROMPT.md` | Prompt to hand to another agent. |
| `evidence/EVIDENCE-TEMPLATE.md` | Output format for proof/evidence. |

## Definition Of Done

The eval path distinguishes good runs from weak or unsafe runs and routes
reviewable failures to the correct owner. Another agent should be able to lift
this design into a work environment and collect comparable evidence without
using private values in public artifacts.
