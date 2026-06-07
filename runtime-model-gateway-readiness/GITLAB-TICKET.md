# GitLab Ticket: Run Runtime Model Gateway Readiness Preflight

## Summary

Run the non-mutating runtime preflight before SRE demos, A2A fanout, chaos, or
GitOps PR proof.

## Feature

The readiness workflow should prove kagent agents, model backends, Agent
Gateway, A2A, and required MCP servers are usable before downstream work starts.

## Evidence Required

- kagent agent readiness.
- ModelConfig status.
- Model backend response.
- Agent Gateway route response.
- A2A `message/send` result.
- Grafana/GitLab/memory MCP status.
- Blocker list.

## Acceptance Criteria

- `RUNTIME_PREFLIGHT_STARTED: yes`
- `KAGENT_AGENTS_READY: yes_or_blocked`
- `MODEL_CONFIG_ACCEPTED: yes`
- `MODEL_BACKEND_READY: yes_or_blocked`
- `AGENTGATEWAY_ROUTE_READY: yes_or_blocked`
- `A2A_SMOKE_COMPLETED: yes_or_blocked`
- `GRAFANA_MCP_ACCEPTED: yes`
- `GITLAB_MCP_ACCEPTED_OR_LITE_FALLBACK: yes_or_blocked`
- `READINESS_BLOCKERS_RECORDED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not treat `Ready=True` or `Accepted=True` alone as runtime proof. A live
response is required.
