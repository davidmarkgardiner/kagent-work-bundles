# Python implementation decision

Status: **proposed implementation direction, based on current Microsoft Agent
Framework documentation checked 2026-08-13.**

## Decision

Use the existing Python Harness implementation in [run.py](run.py) as the
single implementation to progress for this POC. Do not replace it with the Go
coordinator.

This selects the language that can use the documented Agent Framework features,
instead of rebuilding them as a custom control plane.

## Capability comparison

| Capability | Python | Go | Decision |
| --- | --- | --- | --- |
| Harness coordinator | **Verified lab POC:** `run.py` created a Python Harness Agent and called a fixed kagent A2A specialist after approval. | **Verified lab POC:** a direct Go coordinator called fixed A2A specialists. | Python is the implementation route. |
| Packaged bounded looping | **Verified current documentation capability.** | **Verified current documentation boundary:** the packaged looping guide says it is not currently available in Go. | Use Python's documented bounded looping, with explicit maximum iterations. |
| Framework evaluation | **Verified current documentation capability.** | **Verified current documentation boundary:** Go is marked unsupported in the evaluation capability table. | Add a small Python evaluator next; retain deterministic receipt checks as a separate safety gate. |
| OpenTelemetry | **Verified current documentation capability:** traces, logs, metrics, and MCP trace propagation are documented for Python. | No Go implementation is supplied on the current observability page. | Add Python OpenTelemetry only after telemetry destination and redaction are approved. |
| Kubernetes scaling | **Proposed design:** Jobs/Argo control execution lifecycle; Kubernetes resource limits and concurrency controls control scale. | Same. | One active execution per durable request state; no parallel writers. |

References: [looping](https://learn.microsoft.com/en-us/agent-framework/agents/looping?pivots=programming-language-go), [evaluation](https://learn.microsoft.com/en-us/agent-framework/agents/evaluation), [observability](https://learn.microsoft.com/en-us/agent-framework/agents/observability?pivots=programming-language-go).

## What we keep

- The live Python approval-to-kagent proof and its least-privilege boundaries.
- `loop_max_iterations=2` in `make_harness()`.
- The raw A2A envelope, fixed-agent routing, receipt format, and explicit
  approval boundary proven by the Go companion.
- The principle that an Argo Workflow performs any remediation; the Harness
  coordinator only waits for an immutable terminal receipt.

## What we do not claim yet

- A full five-stage long-running factory is not proven. The previous factory
  run queued/cancelled controller-side kagent work, so it remains unsuitable as
  the production execution substrate.
- The native Python evaluation API is not yet wired into this bundle.
- No OpenTelemetry collector/exporter, Azure Monitor destination, or
  prompt/response telemetry policy is deployed.
- No real UK8S health inspection has been proved; the recheck specialist uses
  a synthetic fixture.

## Next bounded Python work

1. Add a Python receipt evaluator with explicit pass/fail criteria: approved
   request, named terminal Argo receipt, one remediation loop, and all required
   A2A receipts.
2. Add an Agent Framework Python evaluator only for the quality judgement that
   deterministic receipts cannot make. Keep it bounded and retain the
   deterministic gate as mandatory.
3. Configure OpenTelemetry to an approved collector with sensitive prompts,
   tool arguments, and tool results disabled by default. Demonstrate a trace
   ID across Harness -> kagent/A2A -> MCP only after the collector path is
   live.
4. Run every stateful stage as a short Argo task, persisting state between
   stages. Do not use one long controller-mediated A2A chain.

This gives us the useful Agent Framework features without turning the Harness
into an unbounded scheduler or granting it Kubernetes mutation permissions.
