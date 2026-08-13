# Go coordinator extension: bounded retry, evaluation, and observability

Status: **live-verified synthetic lab POC; not a claim of Microsoft Agent
Framework Go feature parity.**

This directory provides a small Go coordinator above fixed kagent A2A agents.
It persists receipts and waits for a terminal receipt from a separate,
approval-gated Argo remediation workflow. The coordinator has no Kubernetes
credentials and cannot launch or rerun remediation.

## What is verified

On 2026-08-13, the HomeLab run demonstrated:

1. Two failed calls to a deliberately nonexistent primary `summarise` agent.
2. One successful call to the explicitly configured fallback
   `maf-go-issue-summariser`.
3. Successful terminal A2A receipts for triage, baseline health, and
   post-remediation health.
4. A real synthetic Argo workflow receipt with `state: Succeeded`.
5. A deterministic receipt evaluation with `result: PASS` and exactly one
   remediation loop.

The full output is recorded in [evidence/LIVE-RUN-2026-08-13.md](evidence/LIVE-RUN-2026-08-13.md).
The health agents return deliberately synthetic responses; this is not proof
of a real UK8S health inspection.

## Control contract

| Concern | Implemented POC behaviour | Boundary |
| --- | --- | --- |
| Retry | At most two calls to the named stage agent | Failed attempts are separate receipts; no hidden retry loop. |
| Fallback | One optional, explicitly named `*_FALLBACK_AGENT` | Operator must select an equivalent approved agent; no discovery or model-selected fallback. |
| Circuit breaker | Stage becomes `BLOCKED` after retry/fallback is exhausted | It does not proceed to remediation. |
| Remediation | A pre-approved external Argo workflow leaves a terminal receipt | The coordinator cannot create, retry, or alter a workflow. |
| Evaluation | `MODE=evaluate` checks receipt completeness and one-loop safety | This is deterministic Go code, not an LLM judge. |
| Observability | Per-attempt JSON receipts include agent, HTTP status, fallback source, error, and timestamp. `RECORD_RESPONSE_EXCERPT=true` adds a bounded excerpt for a controlled lab diagnostic run. | No automatic OpenTelemetry exporter is wired in this Go POC. |

## Microsoft Agent Framework capability boundary

| Capability | Current documentation finding | POC decision |
| --- | --- | --- |
| Looping | **Verified current documentation capability boundary.** The current Looping guide states the packaged looping capability is not currently available in Go. | Use the bounded retry/fallback state machine here; never create an unbounded self-loop. |
| Evaluation | **Verified current documentation capability boundary.** The current Evaluation capability table marks Go unsupported. | Use receipt-based deterministic evaluation; a semantic/LLM evaluator would be an explicit later addition. |
| Observability | **Verified current documentation capability** for Agent Framework generally: OpenTelemetry traces, logs, and metrics. The supplied examples and automatic MCP trace propagation are C#/Python-oriented, with no Go implementation on the current page. | Persist safe, minimal receipts now. Add standard Go OpenTelemetry instrumentation/export only after selecting an approved collector/backend and data-redaction policy. |
| Scaling | **Proposed design.** Kubernetes controls process scaling (resources, Deployment/Job parallelism, HPA) rather than an autonomous agent loop. | Keep one coordinator execution per approved request/state directory; do not scale duplicate writers. |

Microsoft references: [looping](https://learn.microsoft.com/en-us/agent-framework/agents/looping?pivots=programming-language-go), [evaluation](https://learn.microsoft.com/en-us/agent-framework/agents/evaluation), and [observability](https://learn.microsoft.com/en-us/agent-framework/agents/observability?pivots=programming-language-go). These pages were checked on 2026-08-13.

## Reproduce against the lab

Prerequisites: the three agents in `synthetic-specialists.yaml` are Ready, the
synthetic workflow in `synthetic-remediation-workflow.yaml` has already been
operator-approved and reached `Succeeded`, and a port-forward reaches the
kagent controller.

```bash
kubectl --context {{CONTEXT}} -n kagent port-forward svc/kagent-controller 38083:8083

state_dir=$(mktemp -d)
KAGENT_A2A_BASE_URL=http://127.0.0.1:38083/api/a2a/kagent STATE_DIR="$state_dir" MODE=request go run .
STATE_DIR="$state_dir" WORKFLOW_NAME={{WORKFLOW_NAME}} WORKFLOW_NAMESPACE=test-remediation go run ./cmd/remediation-receipt
KAGENT_A2A_BASE_URL=http://127.0.0.1:38083/api/a2a/kagent STATE_DIR="$state_dir" MODE=approve \
  ISSUE_SUMMARISER_AGENT=missing-primary \
  SUMMARISE_FALLBACK_AGENT=maf-go-issue-summariser go run .
KAGENT_A2A_BASE_URL=http://127.0.0.1:38083/api/a2a/kagent STATE_DIR="$state_dir" MODE=evaluate go run .
```

Inspect `go-a2a-*-attempt-*-receipt.json`, `go-harness-run.json`,
`remediation-receipt.json`, and `go-harness-evaluation.json` under
`$state_dir`. Treat response excerpts as potentially sensitive operational
data: they are off by default, require `RECORD_RESPONSE_EXCERPT=true`, and
must stay on an access-controlled state volume. Do not export prompts or
responses by default.

## Local checks

```bash
go test .
sh scripts/verify-live.sh {{CONTEXT}}
```

The verifier checks live specialist readiness only; it deliberately does not
claim a new live run from static manifests or historical receipts.
