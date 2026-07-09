# Critique Prompt: Agentic Triage Smoke Tests

You are an independent critical reviewer. Review the agentic triage smoke-test
bundle and evidence in read-only mode.

Do not edit files. Do not browse. Do not assume live validation unless the
evidence explicitly shows commands, workflow names, Grafana alert state, queries,
payloads, logs, screenshots, or scored outputs. Treat absent evidence as not
proven, even if the runbook says the test should exist.

Read:

```text
work-agent-bundles/agentic-triage-smoke-tests/README.md
work-agent-bundles/agentic-triage-smoke-tests/FRONT-SHEET.md
work-agent-bundles/agentic-triage-smoke-tests/SMOKE-RUNBOOK.md
work-agent-bundles/agentic-triage-smoke-tests/SOURCE-TYPE-ALERT-EXAMPLES.md
work-agent-bundles/agentic-triage-smoke-tests/SCORECARD.md
work-agent-bundles/agentic-triage-smoke-tests/evidence/EVIDENCE-TEMPLATE.md
work-agent-bundles/agentic-triage-smoke-tests/CHECKLIST.md
work-agent-bundles/agentic-triage-smoke-tests/examples/monitoring/agentic-triage-smoke-rules.yaml
work-agent-bundles/agentic-triage-smoke-tests/examples/grafana/source-type-alert-rules.yaml
work-agent-bundles/agentic-triage-smoke-tests/examples/alertmanager-payloads/
work-agent-bundles/agentic-triage-smoke-tests/evidence/PROXMOX-E2E-SMOKE-2026-07-09.md
work-agent-bundles/agentic-triage-smoke-tests/evidence/PROXMOX-KIMI-A2A-AND-CONTROL-PLANE-RECOVERY-2026-07-09.md
platform/agentgateway/OPENAI-COMPATIBLE-PROVIDERS.md
platform/agentgateway/backend-openai-compatible-external-models.yaml
platform/agentgateway/modelconfig-openai-compatible-external-models.yaml
```

Critical audit questions:

1. Does the evidence prove the actual claim
   `pod failure -> Grafana metric alert -> webhook/EventSource -> Argo Workflow -> smart-triage fan-out -> agentgateway Kimi route -> HITL/eval success`?
   Return per-hop status for:
   `pod failure`, `Grafana alert`, `webhook/EventSource`, `Argo Workflow`,
   `smart-triage fan-out`, `agentgateway/model route`, and `HITL/eval`.
2. Does the evidence prove only alert delivery, or does it prove agent
   correctness with source-backed output and eval scoring?
3. Does the bundle clearly distinguish live-proven source types from planned
   source types?
4. Is there live evidence for real Grafana-origin Loki log alerts? If not,
   mark logs as not proven.
5. Is there live evidence for real Grafana-origin Kubernetes event alerts? If
   not, mark events as not proven.
6. Is there live evidence for real Tempo trace alerts? If not, distinguish
   `NO_TRACE` fallback from real trace coverage.
7. Is the worker-capacity fix sufficient and documented well enough to avoid
   reintroducing control-plane pressure during periodic runs?
8. Are agentgateway provider manifests and ModelConfigs plausible for
   OpenAI-compatible Kimi, GLM/ZAI, and MiniMax use without leaking secrets?
9. Can the periodic smoke mode produce a programmatic pass score and alert when
   the smoke system itself is stale, degraded, or broken?
10. Are negative cases present so the team knows failures alert visibly?
11. Are read-only, HITL, GitOps, namespace, and public-safety boundaries
    preserved?
12. Are any fields missing that would prevent joining Grafana, Argo, kagent,
    agentgateway, ticket, and eval evidence by `run_id` or fingerprint?

Return exactly this structure:

```text
VERDICT: pass|revise|block

VERDICT_REASON:
- ...

CLAIMS_AUDIT:
- claim: ...
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
  gap: ...

PER_HOP_STATUS:
- hop: pod failure
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
- hop: Grafana alert
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
- hop: webhook/EventSource
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
- hop: Argo Workflow
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
- hop: smart-triage fan-out
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
- hop: agentgateway/model route
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"
- hop: HITL/eval
  status: proven|partially_proven|not_proven
  evidence:
    - path or path:line: "short quoted snippet"

CONTRADICTIONS:
- ...

MISSING_LIVE_SMOKES:
- source: metrics|logs|events|traces|negative-health|periodic
  required_evidence: ...
  current_status: proven|partially_proven|not_proven

SAFETY_CONCERNS:
- ...

OPERABILITY_GAPS:
- ...

DASHBOARD_OR_ALERT_GAPS:
- ...

PUBLIC_SAFETY_ISSUES:
- ...

JOIN_KEYS_STATUS:
- key: run_id|fingerprint|workflow_name|ticket_id|model_usage
  status: consistent|partial|missing
  gap: ...

RECOMMENDED_PATCHES:
- path: ...
  change: ...
```

Reviewer rules:

```text
Use exact file paths and line numbers.
Prefer "not_proven" over inference.
Do not give credit for planned tests unless evidence exists.
Block if the core seven-hop chain is not_proven.
Revise if any of logs, events, traces, negative-health, or periodic are not_proven.
Pass only if the core chain and all claimed source types are proven.
Cap evidence to three entries per claim.
Do not expose or request secrets.
Keep private hostnames, private IPs, internal URLs, and tokens out of your output.
```
