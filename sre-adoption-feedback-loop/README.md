# SRE Adoption Feedback Loop

## TL;DR

Moves Kagent triage v2 from engineering proof into SRE use by onboarding one
application, running an exercise, capturing feedback, and routing improvements.

## What This Feature Does

- Identifies one SRE owner and application.
- Runs the first-contact workflow.
- Runs a controlled incident or game-day exercise.
- Captures feedback and improvement items.
- Reports whether SRE used the workflow.

## Evidence To Produce

- SRE owner and application.
- First-contact run result.
- Exercise result.
- Feedback items.
- Improvement routing.
- Adoption report and metrics/dashboard update.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Run runtime readiness first.
3. Use `WORK-AGENT-START-PROMPT.md`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

SRE has actually used the workflow, provided feedback, and the feedback has a
clear route into tickets, KB, skills, dashboards, evals, or governance changes.
