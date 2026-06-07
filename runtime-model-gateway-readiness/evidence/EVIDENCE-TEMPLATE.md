# Runtime Model Gateway Readiness Evidence

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

## Runtime Summary

- Kubernetes context: `{{KUBE_CONTEXT}}`
- kagent namespace: `{{KAGENT_NAMESPACE}}`
- ModelConfig: `{{CHAT_MODEL_CONFIG}}`
- Agent Gateway: `{{AGENTGATEWAY_HOST}}`
- A2A endpoint: `{{KAGENT_A2A_ENDPOINT}}`

## Evidence

| Check | Result | Evidence |
|---|---|---|
| kagent agents | `{{KAGENT_AGENT_READINESS_RESULT}}` | `{{KAGENT_AGENT_READINESS_EVIDENCE}}` |
| model config | `{{MODEL_CONFIG_RESULT}}` | `{{MODEL_CONFIG_EVIDENCE}}` |
| model backend | `{{MODEL_BACKEND_RESULT}}` | `{{MODEL_BACKEND_EVIDENCE}}` |
| Agent Gateway | `{{AGENTGATEWAY_RESULT}}` | `{{AGENTGATEWAY_EVIDENCE}}` |
| A2A smoke | `{{A2A_SMOKE_RESULT}}` | `{{A2A_SMOKE_EVIDENCE}}` |
| Grafana MCP | `{{GRAFANA_MCP_RESULT}}` | `{{GRAFANA_MCP_EVIDENCE}}` |
| GitLab MCP | `{{GITLAB_MCP_RESULT}}` | `{{GITLAB_MCP_EVIDENCE}}` |
| Memory MCP | `{{MEMORY_MCP_RESULT}}` | `{{MEMORY_MCP_EVIDENCE}}` |

## Go/No-Go

- Decision: `go|no_go|go_with_blockers`
- Blockers: `{{READINESS_BLOCKERS}}`
- Next action: `{{NEXT_ACTION}}`
