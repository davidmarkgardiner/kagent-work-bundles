# Prompt: Run Runtime Model Gateway Preflight

```text
Run the Kagent triage v2 runtime preflight.

Inputs:
- kube context: {{KUBE_CONTEXT}}
- kagent namespace: {{KAGENT_NAMESPACE}}
- model config: {{CHAT_MODEL_CONFIG}}
- Agent Gateway host/route: {{AGENTGATEWAY_HOST}}
- model backend namespace: {{MODEL_BACKEND_NAMESPACE}}
- model backend selector: {{MODEL_BACKEND_SELECTOR}}
- A2A endpoint: {{KAGENT_A2A_ENDPOINT}}
- A2A timeout seconds: {{A2A_SMOKE_TIMEOUT_SECONDS}}
- Grafana MCP: {{GRAFANA_MCP_REMOTE_SERVER_NAME}}
- GitLab MCP: {{GITLAB_MCP_REMOTE_SERVER_NAME}}
- GitLab lite fallback MCP: {{GITLAB_LITE_MCP_REMOTE_SERVER_NAME}}
- Memory MCP: {{MEMORY_MCP_REMOTE_SERVER_NAME}}

Return:
1. kagent agent readiness and any Unknown/False agents.
2. ModelConfig Accepted state and the actual backend pod/service readiness.
3. Agent Gateway route status and any route/backend errors.
4. A2A smoke result: completed, timeout, malformed, or blocked.
5. Grafana MCP Accepted state and required read tools.
6. GitLab MCP Accepted state; if official MCP is blocked, say whether the lite
   fallback is accepted and exactly which tools it supports.
7. Memory MCP Accepted state and whether write/delete tools are limited to a
   curator path.
8. A short go/no-go decision for downstream bundles.

Rules:
- Do not mutate cluster state.
- Do not read or print secret values.
- Do not claim readiness from CRD acceptance alone.
- If model pod readiness or A2A smoke fails, block downstream live demos.
```
