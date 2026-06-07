# Reference

Use these local source areas when implementing or proving runtime readiness:

- `platform/agentgateway/work-qwen-primary-gpt4-failover-handoff/`
- `observability/agent-evals/deepeval/README.md`
- `observability/agent-evals/ARGO-RUNTIME.md`
- `a2a/smart-triage-fanout-demo/workflow-template.yaml`
- `work-agent-bundles/a2a-smart-triage-workflows/`
- `work-agent-bundles/policy-governance-safety/`

## Why This Bundle Exists

The other bundles can pass static verification while live runtime is still
blocked. Common examples:

- ModelConfig is Accepted, but the model backend pod is not Ready.
- Agent service health returns OK, but A2A message/send times out.
- RemoteMCPServer exists, but Accepted=False due to auth or transport failure.
- MCP server is accepted, but exposes broader write tools than the agent should
  be allowed to use.

Run this bundle before SRE game-day, A2A fanout, Grafana evidence, GitLab PR,
KB, memory, eval, or remediation demos.

## Suggested Non-Mutating Commands

```bash
kubectl config current-context
kubectl get agents -A
kubectl get modelconfigs -A
kubectl get pods,svc -n {{MODEL_BACKEND_NAMESPACE}} -l '{{MODEL_BACKEND_SELECTOR}}'
kubectl get pods,svc -n agentgateway-system
kubectl get remotemcpservers -n {{KAGENT_NAMESPACE}}
kubectl logs -n {{KAGENT_NAMESPACE}} deploy/kagent-controller --since=20m
```

For A2A, use the same JSON-RPC `message/send` shape used by
`a2a/smart-triage-fanout-demo/workflow-template.yaml`.
