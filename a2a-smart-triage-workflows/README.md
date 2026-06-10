# A2A Smart Triage Workflows

## TL;DR

Proves that the incident commander can fan out to specialist agents over A2A,
preserve context, and return one synthesized answer with evidence and safety
state.

For the final handover demo, this bundle can act as the walkthrough controller:
it should prove the already-built integrations rather than build new features.

## What This Feature Does

- Sends one incident request to the smart-triage front door.
- Routes the request to Kubernetes, Grafana, knowledge, and GitOps specialists.
- Demonstrates the work-lab integrations that are already in place:
  querydoc/vector KB, Grafana MCP, GitLab MCP, memory, HITL, chaos, lifecycle
  evaluation, and evidence reporting.
- Collects each specialist result into one commander synthesis.
- Records whether remediation is read-only, GitOps/HITL-gated, or blocked.

## Evidence To Produce

- Runtime preflight result from `../runtime-model-gateway-readiness/`.
- A2A endpoint, payload, task/session ID, and response summary.
- Specialist completion markers.
- Querydoc/vector KB cited answer.
- Grafana MCP query/dashboard or panel evidence.
- GitLab MCP issue/MR/comment/code-update evidence.
- Memory seed/recall evidence if memory is installed.
- HITL approval/suspend evidence or pending Teams-channel blocker.
- Chaos-to-eval evidence if the demo includes the reliability loop.
- Final synthesis with cited evidence and sanitized output.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Run the runtime readiness bundle first.
3. Use `WORK-AGENT-START-PROMPT.md`.
4. Use `prompts/02-final-demo-walkthrough.md` for the last-day walkthrough.
5. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

All required A2A markers are present, the final answer is synthesized rather
than a set of disconnected specialist replies, and no write action is claimed
without an explicit GitOps or HITL boundary.
