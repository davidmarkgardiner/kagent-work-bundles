# A2A Smart Triage Workflows

## TL;DR

Proves that the incident commander can fan out to specialist agents over A2A,
preserve context, and return one synthesized answer with evidence and safety
state.

## What This Feature Does

- Sends one incident request to the smart-triage front door.
- Routes the request to Kubernetes, Grafana, knowledge, and GitOps specialists.
- Collects each specialist result into one commander synthesis.
- Records whether remediation is read-only, GitOps/HITL-gated, or blocked.

## Evidence To Produce

- Runtime preflight result from `../runtime-model-gateway-readiness/`.
- A2A endpoint, payload, task/session ID, and response summary.
- Specialist completion markers.
- Final synthesis with cited evidence and sanitized output.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Run the runtime readiness bundle first.
3. Use `WORK-AGENT-START-PROMPT.md`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

All required A2A markers are present, the final answer is synthesized rather
than a set of disconnected specialist replies, and no write action is claimed
without an explicit GitOps or HITL boundary.
