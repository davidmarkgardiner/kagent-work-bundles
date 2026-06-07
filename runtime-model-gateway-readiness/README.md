# Runtime Model Gateway Readiness

## TL;DR

Non-mutating preflight that proves kagent, model backends, Agent Gateway, A2A,
and required MCP servers are live before any downstream demo starts.

## What This Feature Does

- Checks kagent agent readiness.
- Confirms ModelConfig acceptance.
- Proves the model backend can answer.
- Proves Agent Gateway route can answer.
- Proves A2A `message/send` completes.
- Checks required MCP servers and tools.

## Evidence To Produce

- Agent readiness.
- Model route response.
- Agent Gateway response.
- A2A task/session and response.
- Grafana/GitLab/memory MCP status.
- Blocker list if anything fails.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/runtime-readiness-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

Downstream SRE, chaos, A2A, GitOps, and observability demos only proceed when
the live runtime path answers, or blockers are clearly recorded.
