# Front Sheet: Agentic Triage Smoke Tests

## Goal

Prove a new agentic triage installation works end to end before real alert
traffic is routed to it.

## Non-Goals

- Do not prove production self-healing on day one.
- Do not grant write-capable tools to read-only smoke agents.
- Do not replace existing app runbooks.
- Do not claim trace coverage if Tempo or trace IDs are unavailable.

## Primary Question

Can Grafana-origin signals for metrics, logs, events, and traces reach the
agentic triage system, produce source-backed agent output, score cleanly, and
surface health or failure in Grafana?

## Current Status

Live evidence proves the metrics crashloop alert-intake path through Grafana
alert delivery, webhook/EventSource intake, Argo workflow creation, and
incident normalization. That run failed at the agent path.

A separate manual fan-out run proves agentgateway Kimi model routing,
smart-triage specialist completion, HITL resume, and lifecycle eval success.
No single continuous `run_id` yet proves crashloop alert intake through Kimi
fan-out and eval success.

Kubernetes event alerts through Alloy/Loki/Grafana are now live-proven. Trace
coverage is fallback-only: `TRACE_FALLBACK: NO_TRACE` was captured, but no real
Tempo trace ID or deeplink exists.

Loki application log alerts are still not proven. A real log marker was emitted
by a smoke pod, but Promtail did not deliver it to Loki during the smoke window.
Do not mark full source coverage green until the log pipeline is fixed and a
real Grafana LogQL alert reaches smart triage.

No alert-to-GitLab-ticket path is proven in this bundle. Any GitLab/ticket
markers in demo lifecycle output are placeholders or simulated hygiene markers
unless backed by a ticket-system API call evidence file.

## Key Paths

```text
work-agent-bundles/agentic-triage-smoke-tests/SMOKE-RUNBOOK.md
work-agent-bundles/agentic-triage-smoke-tests/evidence/EVIDENCE-TEMPLATE.md
work-agent-bundles/agentic-triage-smoke-tests/prompts/CRITIQUE-PROMPT.md
```

## Decision

Use the verdict labels from `work-agent-bundles/kagent-agentic-cluster-smoke-tests.md`:

```text
red   = no real alert traffic
amber = synthetic or low-risk route only
green = eligible for staged real alert traffic
```

## Periodic Health Decision

Use a separate recurring verdict for the stack health check:

```text
healthy   = latest scheduled smoke passed and no hard failures
degraded  = smoke score below threshold, stale completion, or source gap
broken    = model, A2A, webhook, workflow, or eval path failed
```
