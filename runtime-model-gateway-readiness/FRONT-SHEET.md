# Runtime Model Gateway Readiness Work-Agent Bundle

Purpose: prove kagent, Agent Gateway, model backends, MCP servers, and A2A
front doors are actually usable before any SRE handover, game-day, triage, or
remediation demo relies on them.

## One-Line Ask

Run a non-mutating live preflight that proves kagent agents are ready, required
RemoteMCPServers are accepted with expected tools, the model route can answer
within timeout, A2A message/send completes, and any blocked runtime dependency
is recorded before downstream bundles start.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/runtime-readiness-request.yaml`
5. `prompts/01-run-runtime-model-gateway-preflight.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

## Required Markers

```text
RUNTIME_PREFLIGHT_STARTED: yes
KAGENT_AGENTS_READY: yes_or_blocked
MODEL_CONFIG_ACCEPTED: yes
MODEL_BACKEND_READY: yes_or_blocked
AGENTGATEWAY_ROUTE_READY: yes_or_blocked
A2A_SMOKE_COMPLETED: yes_or_blocked
GRAFANA_MCP_ACCEPTED: yes
GITLAB_MCP_ACCEPTED_OR_LITE_FALLBACK: yes_or_blocked
MEMORY_MCP_ACCEPTED: yes_or_not_required
READINESS_BLOCKERS_RECORDED: yes
OUTPUT_SANITIZED: yes
```

## Definition Of Done

- Do not treat `ModelConfig Accepted=True` as proof that the model can answer.
- Do not treat an agent `Ready=True` as proof that A2A completes.
- Do not treat an MCP server name as usable unless it is `Accepted=True` and
  exposes the required tools.
- If an A2A or model smoke times out, block downstream demos until model/backend
  readiness is fixed or an approved fallback model is selected.

Static verification proves this bundle is internally consistent. It does not
prove live model, Agent Gateway, A2A, MCP, or cluster behavior.
