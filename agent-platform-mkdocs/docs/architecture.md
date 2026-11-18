# Platform architecture and KRO

## Delivered platform foundation

The pod lead confirms that teams already have a self-service agent-onboarding service and AI-enabled operational workflows. The [historical record](historical-achievements.md) lists the delivered capability. The architecture below describes ownership and the reviewed evolution path, including the newer runtime; it does not imply the platform starts from zero.

```text
Human / SRE chat             Incident event / ServiceNow
         |                            |
 interactive session          durable incident workflow
         +-------------+--------------+
                       |
        authenticated and authorised gateway entry
                       |
              kagent Agent (1.0 API)
         AgentTemplate + platform Harness
                       |
           Session -> Substrate Actor
          WorkerPool / sandbox / snapshots
                       |
          approved model and MCP routes
                       |
       backend identity + resource authorisation
```

The diagram describes responsibilities rather than a validated network topology. Substrate also contains its own networking/egress components; those are distinct from the separately managed platform agentgateway front door.

## Who owns what

| Layer | Platform responsibility | Agent/service owner responsibility |
| --- | --- | --- |
| KRO composition | Reviewed input schema and generated resources | Supply owner, supported profile, tool scopes and usage limits |
| kagent | CRDs, controller, Harnesses, supported runtime images and shared capacity | AgentTemplate behaviour and approved configuration changes |
| Substrate | Workers, atelet, identity material, snapshot store, placement and lifecycle | Use the approved execution profile |
| agentgateway | A2A/MCP/model routes, policies, cross-namespace grants and telemetry | Request named routes and justified permissions |
| MCP/API backend | Tool contract, destination enforcement and backend credentials | Domain-specific read contract and evidence quality |
| GitOps and Argo | Flux reconciliation, fixed execution workflows and scoped service accounts | Submit typed requests; review operational outcomes |

## KRO is composition, with explicit authority

KRO composes reviewed Kubernetes desired state; ASO owns approved Azure resource lifecycle and Flux owns reconciliation. Supplying a UAMI ID is not proof of ownership or authority to bind it. Identity provisioning/grants require separately owned automation. Validate ResourceGraphDefinition API/CEL against the selected KRO release; no KRO version bump or workplace reconcile is implied by this docs refresh.

The existing secure KRO/classic-kagent and four-CRD bundles remain design/reference inputs. They do not become 1.0-compatible by changing an image tag. Regenerate the produced AgentTemplate/Harness/Agent and model/tool bindings, validate them against 1.0.1 CRDs, then test the complete onboarding path. Preserve work-side deployed names and approved wiring unless migration requires an owned change.

## Supported profiles

Begin with platform-managed read-only native agents. Add a BYO image or framework only after the image, A2A contract, shutdown/snapshot behaviour, tools, identity and egress have passed acceptance. CrewAI is a framework option; our specialist crew does not require CrewAI. Isolation comes from runtime and destination controls, with separately proven policies.
