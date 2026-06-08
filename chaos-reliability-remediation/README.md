# Chaos Reliability Remediation

## TL;DR

Lets SRE request a controlled lower-environment failure, prove Kagent triage
detects and explains it, gate remediation through HITL/GitOps, verify recovery,
and produce a scored report.

## What This Feature Does

- Runs an approved chaos or regression scenario against a non-production target.
- Collects cluster and Grafana evidence.
- Routes triage through Kagent.
- Blocks remediation until HITL or GitOps review.
- Scores the run and produces a report.

## Evidence To Produce

- Approved non-production target.
- Chaos injection record.
- Triage and Grafana evidence.
- HITL/GitOps remediation boundary.
- Recovery verification.
- Lifecycle eval/report output.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Run runtime readiness first.
3. Use `WORK-AGENT-START-PROMPT.md`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## YAML Examples

Use `examples/` for concrete work-side starting points:

- `examples/chaos-test-pod-delete.yaml`
- `examples/litmus-chaosengine-pod-delete.yaml`
- `examples/argo-workflow-dry-run.yaml`
- `examples/a2a-chaos-request-payload.json`

Keep `dry_run: "true"` until runtime readiness, target opt-in, and HITL are
proven in the work environment.

## Definition Of Done

The controlled failure is injected, detected, triaged, gated, recovered, scored,
and reported without unsafe production mutation.
