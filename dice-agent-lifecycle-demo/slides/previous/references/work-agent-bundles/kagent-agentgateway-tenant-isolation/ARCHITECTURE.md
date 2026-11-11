# Architecture

## Selected shape

One platform namespace owns a dedicated Gateway with five listeners. Event A2A, event MCP, chat A2A, chat MCP, and platform Substrate A2A each get a separate port and policy target. The listeners accept routes only from the platform Gateway namespace. Team namespaces cannot attach a route even if a future RBAC error grants `HTTPRoute` creation.

```text
event webhook or chat client
          |
          v
platform Gateway listener
  strict JWT plus claim policy
          |
    A2A HTTPRoute
          |
tenant-kagent-controller:8083
          |
  team Agent runtime
          |
platform MCP listener
  strict service JWT plus tool policy
          |
AgentgatewayBackend plus ReferenceGrant
          |
 team MCP Service
```

The fifth path is deliberately narrower:

```text
approved platform reviewer
          |
substrate-a2a listener :8085
  strict JWT plus claim policy
          |
exact path rewrite and ReferenceGrant
          |
kagent/kagent-controller:8083
          |
machinist-security-review SandboxAgent
          |
restore golden actor -> answer -> suspend snapshot
```

The platform route rewrites an entire dedicated A2A listener to the exact kagent controller path `/api/a2a/<namespace>/<agent>/`. The trailing slash is intentional. The MCP route crosses into a platform-owned `AgentgatewayBackend` stored in the team namespace. A `ReferenceGrant` allows `HTTPRoute` objects from the exclusively platform-owned gateway namespace to reference that named backend. The backend then uses a namespace-local typed reference to the team's MCP Service. Agentgateway v1.5 does not support a namespace field on an MCP target's `static.backendRef`, so the backend cannot remain central. The grant can name the target backend but cannot name one source route.

## Why this beat a Gateway in every team namespace

A team-local Gateway removes routine cross-namespace references but places platform data-plane Pods, Services, service accounts, and TLS material beside an application administrator. Workload permissions can then be used to mount or imitate platform assets unless admission covers Pods, every controller template, Secret mounting, service accounts, and reserved labels. The centralized design has a shared data-plane blast radius, but its privilege boundary follows namespace ownership and has less admission surface.

The shared Gateway is dedicated to this bundle. It does not reuse the existing red `ai-gateway`.

The Substrate route is not a generic controller proxy. Its dedicated listener rewrites every request to `/api/a2a-sandboxes/kagent/machinist-security-review/`, and a named ReferenceGrant permits only the shared controller Service. The `kagent` namespace carries the bundle's discovery label so the dedicated agentgateway controller can resolve that one Service reference.

## Ownership

| Resource | Owner | Namespace |
| --- | --- | --- |
| Gateway, HTTPRoutes, policies | platform | `tenant-gateway-system` |
| MCP backend | platform | team namespace, protected by RBAC |
| kagent controller and database | platform | `tenant-kagent-system` |
| Agent and prompt ConfigMap | application team | team namespace |
| executable skill artifact | application team | external OCI registry |
| RemoteMCPServer and MCP bearer Secret | platform | team namespace |
| MCP Deployment and Service | application team | team namespace |
| ReferenceGrant, Role, RoleBinding, NetworkPolicy | platform | target namespace |
| SandboxAgent, ActorTemplate, WorkerPool, snapshots | platform | `kagent` and `ate-system` |

## Identity

A caller token has one A2A audience and `purpose: a2a`. A runtime token has one MCP audience and `purpose: mcp`. Both also carry `tenant` and `sub`. Policies first validate signature, issuer, audience, and expiry, then require the expected tenant, purpose, and subject.

The Substrate caller uses its own `urn:kagent-lab:substrate:a2a` audience, `platform-substrate` tenant claim, and platform-reviewer subject. An ordinary chat token fails authentication on audience; a correctly signed rogue token with the Substrate audience fails authorization on claims.

The red private key exists only in the local temporary run directory. The Gateway policy contains the public JWKS inline. Short-lived runtime tokens are stored in team Secrets because kagent v0.10.1 `RemoteMCPServer.spec.headersFrom` resolves a namespaced Secret. Namespace administrators can read and replace every Secret in their namespace, including these tokens, by design. The tokens authorize only that team's MCP listener; cross-team reuse fails on audience and claim policy. Do not put a credential that must be hidden from a namespace administrator in that namespace.

The red ModelConfigs use copies of one existing lab model-gateway key. That proves the Agent path but does not provide per-team provider attribution or quota. An AKS promotion must issue a distinct workload identity or virtual model-gateway key per team and prove that using one team's credential on the other team's model route is denied.

For AKS, replace the red token issuer with Entra app registrations and workload token acquisition. The native Entra MCP policy is for interactive client discovery and PKCE. The current Kubernetes policy does not accept a confidential-client secret. Runtime token acquisition and refresh remain a separate production gate.

## Network boundary

Each team namespace is deny-all. The gateway may reach only the MCP Pod on 8080. The kagent controller may reach only generated Agent Pods on 8080. Agent Pods may reach DNS, their own MCP Gateway port, and only the existing red model Gateway Pods on port 80. The event adapter may reach DNS and its own A2A Gateway port. A labelled in-cluster event source may reach only the adapter on 8080. Rogue Pods get no cross-namespace egress.

The kagent controller Pods are selected by the exact pinned-chart labels and deny inbound controller access except from the dedicated Gateway Pods and controller-generated Agent Pods that need the session API. This matters because `trusted-proxy` trusts claims already checked upstream. Direct controller reachability would invalidate that trust model. Admission reserves the generated-Agent label path: only the kagent controller may put it in Deployment metadata or a Deployment Pod template, and only the ReplicaSet controller may put it on a Pod. The verifier exercises the harder Pod-template spoof path.

## Admission

RBAC is the primary control. Team roles omit RBAC, Gateway API, agentgateway, NetworkPolicy, ModelConfig, RemoteMCPServer, Secret token requests, impersonation, and namespace mutation.

The bundle uses Kubernetes ValidatingAdmissionPolicy for Agent and RemoteMCPServer reference constraints because red's Kyverno Deployments and webhook configurations are inactive. The same policy makes the shared controller lane declarative-only and reserves the kagent-managed label on Deployments, Deployment Pod templates, and Pods. This prevents a namespace administrator from submitting a BYO image or forging the label that grants the generated runtime its narrow controller path. A workplace cluster with an operated Kyverno installation can translate the same invariants into ClusterPolicies, but adding a second admission engine is not required for this proof.

Pod Security Admission labels all team namespaces `restricted`. A production AKS namespace should also apply its organization image, registry, workload identity, and egress policies.

## Failure semantics

- Missing or invalid JWT: authentication fails with 401.
- Valid JWT with wrong tenant, purpose, or subject: authorization fails with 403.
- Forbidden MCP tool: MCP authorization filters it from discovery and rejects invocation.
- Missing ReferenceGrant: the route reports unresolved references and cannot forward.
- Direct Service call: packet times out or is refused under enforced NetworkPolicy.
- Rogue route: listener attachment is rejected because routes are only allowed from the platform namespace.

The test matrix pairs every denial with a positive control and a backend counter witness where the protocol permits it.

## Current red facts

The red cluster was observed at Kubernetes v1.32.2 with agentgateway v1.1.0, shared kagent 0.10.0-beta7, Agent Substrate 0.0.8, Gateway API v1.4.0, no Istio policy APIs, inactive Kyverno webhooks, and working kindnet NetworkPolicy enforcement. The canary therefore uses parallel agentgateway and ordinary-kagent controller names and namespaces, while the Substrate route intentionally targets the existing platform-owned shared controller.

Only one kagent controller may own a SandboxAgent. A failed integration probe showed that enabling Substrate reconciliation in the parallel v0.10.1 controller while the shared all-namespaces controller remained active created competing ActorTemplates; the v0.10.1 controller also failed against the installed 0.0.8 Substrate API. The probe objects were removed, both orphan actors were deleted, and the integration now preserves single-controller ownership. In the workplace target, move the specialist only as part of the reviewed kagent 0.10.1/Substrate 0.0.9 platform upgrade.
