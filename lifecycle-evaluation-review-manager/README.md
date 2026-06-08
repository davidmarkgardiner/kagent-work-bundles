# Lifecycle Evaluation Review Manager

## TL;DR

Design, build, and verify lifecycle evaluation for Kagent triage/remediation
runs. The bundle covers offline eval, online eval, key metrics, inline versus
separate evaluator architecture, storage/access, audit retention, and
traceability. It also defines the phase-1 proof path from chaos event to agent
triage, lifecycle evaluation, and GitLab evidence.

## What This Feature Does

- Maps the planning-meeting actions to repo design docs.
- Loads lifecycle eval cases and scorer.
- Starts with work-environment variable resolution so private namespaces,
  images, MCP server names, and GitLab targets are not guessed.
- Connects a chaos or Kubernetes event to the Kagent triage lifecycle.
- Scores one passing and one below-threshold run.
- Enforces hard gates such as mutation-before-HITL or missing verification.
- Verifies the online Argo evaluator architecture.
- Documents the event-to-evaluation contract for Argo Events, Litmus, or a
  workflow watcher. Grafana alert triggering is optional for phase 1.
- Confirms the independent metrics library and label policy.
- Defines storage, access, retention, and traceability evidence.
- Produces a review-manager route payload for failing cases and a GitLab
  evidence update for the chaos-tested action.
- Includes `payload/agent-evals` so the scorer, route script, lifecycle cases,
  and sample runs are available even when only this bundle directory is handed
  over.

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
- Chaos event source or watcher proof.
- Triage run ID and lifecycle evaluation result for the chaos-tested action.
- GitLab issue, MR, comment, or report evidence.
- Metrics/report export or blocker.

## How To Run

1. Read `../SHARED-VARIABLES.md` and resolve the private work values needed by
   this bundle.
2. Run `bash scripts/verify-bundle.sh`.
3. Use `WORK-AGENT-START-PROMPT.md`.
4. Fill in `requests/lifecycle-evaluation-request.yaml`.
5. Use `prompts/02-prove-chaos-event-to-eval-gitlab.md` for the end-to-end
   proof.
6. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## File Map

| File | Purpose |
| --- | --- |
| `MEETING-ACTION-COVERAGE.md` | Maps each planning-meeting action to design docs and required evidence. |
| `ARCHITECTURE-DECISION.md` | Explains inline versus separate evaluator and the selected hybrid pattern. |
| `DATA-STORAGE-ACCESS-TRACEABILITY.md` | Defines storage classes, RBAC boundaries, retention, and traceability fields. |
| `IMPLEMENTATION-VERIFY-PLAN.md` | Step-by-step build and verification plan for a work environment. |
| `CHAOS-TO-EVAL-FLOW.md` | Contract for chaos event, triage, lifecycle eval, and GitLab evidence. |
| `WORK-AGENT-START-PROMPT.md` | Prompt to hand to another agent. |
| `HOMELAB-VERIFICATION-EVIDENCE.md` | Local offline, server-dry-run, and online Argo proof collected before handoff. |
| `payload/agent-evals/` | Bundle-local scorer scripts, lifecycle cases, and sample runs. |
| `evidence/EVIDENCE-TEMPLATE.md` | Output format for proof/evidence. |

## Definition Of Done

The eval path distinguishes good runs from weak or unsafe runs and routes
reviewable failures to the correct owner. The work agent must prove a real or
approved dry-run chaos event can be traced through triage, scoring, and GitLab
evidence, or record the exact blocker. Another agent should be able to lift this
design into a work environment and collect comparable evidence without using
private values in public artifacts.
