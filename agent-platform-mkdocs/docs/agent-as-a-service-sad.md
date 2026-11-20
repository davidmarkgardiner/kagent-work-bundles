# Agent-as-a-Service solution architecture

This page is the handbook's public-safe architecture overview for a shared service that lets application teams onboard agents and use approved tools and skills. It brings together the existing multi-namespace design and the current platform guidance. Use the [lab acceptance matrix](labs.md) for evidence requirements at the target release and environment.

## Interactive architecture diagrams

[Open the layered architecture walkthrough](architecture-layers/index.html). Use **Next layer** to add JWT-protected access, Entra workload identity, the central registry, evaluation and observability to the basic service. Select any layer to jump straight to that cumulative view.

The [original DICE walkthrough](architecture-layers/dice-detail.html) includes the more detailed JWT, Entra handshake, telemetry and evaluation diagrams.

## Service boundary

Application teams own the agent's behaviour, its workflow placement and the access they request. Platform operators own the shared controller, runtime profiles, gateway policies and GitOps reconciliation. Tool and data owners approve access and enforce it at the destination. A catalogue entry makes a tool or skill discoverable. An approved binding and runtime authorisation determine whether the agent can use it.

```text
Team GitOps request --> Reviewed KRO composition --> Agent in team namespace
                                                       |
User or workflow --> Authenticated gateway route --> Agent runtime
                                                       |
                              Approved tool binding --> MCP or API backend
                              Approved skill revision --> Agent runtime context
```

A shared service can manage agents in several namespaces. The original design used a shared controller. Current onboarding should use the supported runtime and validated composition in the [version matrix](versions.md) and [Platform architecture and KRO](architecture.md). The topology above describes the service boundaries.

## Onboard, invoke and operate

| Stage | Design | Accountable owner |
| --- | --- | --- |
| Register | Submit the owning team, namespace, runtime profile, requested tools and skills, and intended caller identities through reviewed GitOps. | Application team and platform onboarding owner |
| Compose | KRO produces the supported resources from reviewed inputs. Flux reconciles the approved revision. Platform-owned policies and identities define what tenants can change. | Platform operator |
| Invoke | Route human or workflow calls through the approved gateway entry point. Authenticate the caller and authorise the specific agent destination. | Gateway and agent service owners |
| Use tools | Bind approved tool destinations explicitly. Authorise the agent's outbound identity and enforce resource-level access at the backend. | Tool and data owners |
| Use skills | Resolve a reviewed skill revision from the registry or approved source. Track its provenance and version with the agent configuration. | Registry and agent owners |
| Operate | Correlate request, agent revision, tool calls and outcome. Use an authorised workflow and service account for writes, with review where the workflow requires it. | Service operator and workflow owner |

## Security and acceptance

- Keep namespace administration scoped to the team. Manage cross-namespace routing grants, admission rules and destination policy through platform-owned configuration. Verify a neighbouring tenant cannot invoke the agent or reach its tools.
- Check caller-to-agent and agent-to-tool authorisation separately. Validate the expected issuer, audience and permissions at each boundary. Confirm access is removed after revocation.
- Record the reconciled Git revision, Agent readiness, a successful invocation and the backend receipt for an allowed tool call. Run the corresponding denied cases and keep the receipts with the target release. Use the [identity](identity.md), [isolation](isolation.md) and [lab](labs.md) pages for the checks.

Team onboarding and operational workflows have owner-confirmed delivery history. New runtime, isolation and receiving-service claims depend on the current [acceptance evidence](evidence.md). Treat the source below as a historical design reference. Use the handbook's current deployment and policy guidance for implementation.

## Source architecture

- [Multi-Namespace Agent-as-a-Service design at its original revision](https://github.com/davidmarkgardiner/kagent-public/blob/1cbd475ff2f245c810bf47ec69b9269346631db0/docs/architecture/MULTI-NAMESPACE-AGENT-AS-A-SERVICE.md)
- [Agent platform architecture and KRO](architecture.md)
- [Deploy an agent through the supported path](deploy.md)
