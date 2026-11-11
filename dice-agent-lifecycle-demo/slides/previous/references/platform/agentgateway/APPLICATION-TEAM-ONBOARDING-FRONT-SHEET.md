# Application-team onboarding to agentgateway

Status: design review only. A live onboarding demonstration is not ready until
the authenticated model and namespace-scoped MCP proofs in Phases 1 and 2 of
the [platform design record](APPLICATION-TEAM-ONBOARDING-PLAN.md) have passed.

Meeting owner: `{{PLATFORM_AGENTGATEWAY_OWNER}}`

App Team owner: `{{APPLICATION_TEAM_OWNER}}`

Target proof date: `{{TARGET_PROOF_DATE}}`

## What the App Team gets

- One governed endpoint for an explicitly approved model route.
- An optional MCP endpoint exposing only named, approved tools.
- An optional platform-published model/tool configuration for a namespaced
  kagent Agent after the kagent/A2A identity proof passes.
- Caller, route, policy-decision, latency, and usage telemetry without bearer
  tokens, credentials, secrets, or prompt content unless separately approved.
- A documented owner, support route, expiry date, and revocation procedure.

The first proof is deliberately narrow: one development workload, one model,
one read-only namespace-scoped MCP capability, and no write tools.

## Authentication and authorization

```text
team pod ServiceAccount
  -> federated team UAMI
  -> short-lived JWT for the agentgateway audience
  -> agentgateway validates token and route role
     -> gateway UAMI calls the approved model
     -> MCP backend identity accesses only approved resources
```

The team UAMI is authorised to call agentgateway; it does not receive direct
model access. Federation lets a ServiceAccount become a UAMI, but does not
itself grant access to the gateway, model, MCP, or Kubernetes API.

The platform owns shared routes, policies, backend identities, and credentials.
The App Team owns its workload, namespaced ServiceAccount, client token refresh,
and declared use case.

## What the App Team supplies

Please answer these before implementation:

1. Is the caller an application, kagent Agent, another agent framework, or an
   MCP server?
2. Is the call workload-to-workload or on behalf of an end user?
3. Which cluster, namespace, ServiceAccount, and approved UAMI will call?
4. What exactly is the target model service, model/deployment, region, and API?
5. What data classification is sent, and may prompts/responses be logged?
6. Which MCP servers, exact tools, and target resources are required?
7. Are any actions write-capable, and who approves each mutation?
8. What rate, concurrency, token budget, timeout, and streaming behaviour is
   expected?
9. What private connectivity, DNS, TLS, and corporate CA path is available?
10. Who owns support, incidents, cost review, access review, and offboarding?

## Boundaries

The App Team does not receive permission to:

- edit shared `AgentgatewayBackend`, `HTTPRoute`, `AgentgatewayPolicy`,
  `ModelConfig`, `RemoteMCPServer`, identity, or credential resources;
- send callers directly to a shared MCP Service or model endpoint;
- select an unapproved model, MCP target, tool, namespace, cluster, or
  subscription through request fields;
- use wildcard tools or propagate arbitrary authorization headers; or
- treat a prompt instruction, kagent `toolNames`, or `x-kagent-*` header as a
  security boundary.

Write-capable tools require a separate review, identity, workflow executor,
and approval boundary.

## What this meeting can decide now

- Confirm the consumer pattern and first narrow use case.
- Confirm model, MCP, data, network, cost, and ownership inputs.
- Assign platform, Entra, MCP, kagent, security, and App Team owners.
- Agree target dates for the installed-contract discovery and proof phases.
- Decide whether the next meeting is another design checkpoint or a live proof.

Do not advertise a live allow/deny showcase until strict JWT authentication,
the managed-identity app-role assignment, JWKS connectivity, model routing,
namespace-scoped MCP identity, direct-backend denial, restart/reload behaviour,
and audit redaction have all been evidenced. kagent onboarding additionally
requires authenticated A2A ingress so another pod cannot drive a privileged
Agent as a confused deputy.

## Platform references

- [Full security and delivery design](APPLICATION-TEAM-ONBOARDING-PLAN.md)
- [Independent review](APPLICATION-TEAM-ONBOARDING-PLAN-REVIEW.md)
- [Authentication mechanics](AUTHENTICATION.md)
