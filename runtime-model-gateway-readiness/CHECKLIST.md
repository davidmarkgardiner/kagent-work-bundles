# Runtime Model Gateway Readiness Checklist

| Check | Evidence | Status |
|---|---|---|
| Bundle verifier passes | verifier output | TODO |
| Active context confirmed | `kubectl config current-context` | TODO |
| kagent agents ready | `kubectl get agents -A` | TODO |
| ModelConfig accepted | `kubectl get modelconfig -A` | TODO |
| Model backend ready | pod/service status or blocked reason | TODO |
| Agent Gateway route ready | health/route check or blocked reason | TODO |
| A2A smoke completes | state completed or timeout/error evidence | TODO |
| Grafana MCP accepted | RemoteMCPServer Accepted and tools | TODO |
| GitLab MCP accepted or fallback selected | accepted server/tool list or blocker | TODO |
| Memory MCP accepted if required | RemoteMCPServer Accepted and tools | TODO |
| Blockers recorded | exact owner/next action | TODO |
| Output sanitized | no secrets, tokens, private endpoints, tenant IDs | TODO |
