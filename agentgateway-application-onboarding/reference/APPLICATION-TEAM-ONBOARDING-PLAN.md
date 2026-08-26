# Application-team onboarding to agentgateway

Status: proposed plan for review; no live access or deployment is authorised by
this document.

Audience: platform/security design reviewers. Application teams should begin
with the [application-team front sheet](APPLICATION-TEAM-ONBOARDING-FRONT-SHEET.md).

Document owner: `{{PLATFORM_AGENTGATEWAY_OWNER}}`

Security approver: `{{SECURITY_APPROVER}}`

Entra application-role assignment owner: `{{ENTRA_APPLICATION_ADMIN_OWNER}}`

Target dates: to be agreed before implementation. The owner must add a target
date and accountable person to every delivery phase before work starts.

## Outcome

Provide application teams with one governed gateway for:

- OpenAI-compatible LLM access;
- approved MCP tool discovery and execution; and
- optional kagent Agent hosting in the team's own namespace.

The default design is:

```text
application pod or approved kagent runtime
  -> short-lived Entra JWT for the agentgateway audience
  -> agentgateway authenticates and authorises the caller
     -> model route uses a platform-owned UAMI to call the approved model
     -> MCP route uses a backend-specific identity to call the approved MCP
        -> MCP identity has only its required downstream permissions
```

An application team's Kubernetes namespace permissions do not automatically
constrain an HTTP call through agentgateway. Namespace RBAC governs Kubernetes
API operations in that namespace. Agentgateway route policy, MCP policy,
network policy, and the downstream service identity govern data-plane access.

## Onboarding lanes

Keep the delivery mechanism modular:

1. **Application and model route** — the standard lane. Assume the application
   runs in its own namespace on the agentic cluster, authenticates to
   agentgateway with its workload identity, and uses a platform-owned backend
   identity for the Model Garden connection.
2. **Platform MCP attachment** — an optional extension. The team selects a
   platform-reviewed MCP entry and exact tool names; the platform/MCP owner
   retains the backend credential and resource authorization.
3. **Bring-your-own MCP** — a separate security workflow covering provenance,
   tools, credentials, egress, resource scope and lifecycle. Do not make it a
   checkbox inside ordinary application onboarding.

An application outside the agentic cluster is an exception lane because
private ingress, source identity, DNS/TLS and network containment differ.

## Recommended decisions

1. Use workload JWT authentication for application-to-gateway traffic. API
   keys are a temporary development option, not the production default.
2. Register agentgateway as a protected Entra API with a dedicated audience
   and application roles such as `Model.Invoke` and `Mcp.Read`.
3. Give every onboarded workload a namespaced ServiceAccount and a dedicated
   or approved team UAMI federated only to that ServiceAccount subject.
4. Subject to Phase 0 confirming the target Model Garden endpoint and provider
   contract, assign the caller UAMI roles on the agentgateway API, not direct
   model permissions. Agentgateway uses its own backend UAMI for model access.
5. Create separate gateway routes and policies for each trust or capability
   class. Do not expose one unrestricted `/v1` or `/mcp` endpoint to every
   team.
6. Keep MCP tool-name authorization at agentgateway and resource authorization
   in the MCP server's own identity/RBAC. Block direct access to the MCP
   Service so callers cannot bypass gateway policy.
7. Let teams create kagent `Agent` objects in their namespace only after
   admission policy prevents arbitrary model URLs, arbitrary MCP URLs,
   cross-namespace references, wildcard tools, and unapproved headers.
8. Start with one development team, one model route, one read-only MCP surface,
   and no write-capable tools.

## Four identities, not one

| Boundary | Identity | What it is allowed to do |
|---|---|---|
| Team pod -> agentgateway | Team workload UAMI represented by a short-lived Entra JWT | Call only assigned gateway routes and capabilities |
| Shared kagent -> agentgateway | Initially a platform kagent caller identity; per-agent attribution requires a proven trusted mechanism | Call only routes granted to that kagent trust domain |
| agentgateway -> model provider | Platform-owned backend UAMI | Invoke only approved model resources or projects |
| agentgateway -> MCP -> target | Backend-specific MCP identity and downstream RBAC | Execute only approved tools against approved resources |

Federation and authorization are separate. A federated credential permits one
Kubernetes ServiceAccount to become a UAMI. It does not grant that UAMI access
to agentgateway, a model, an MCP, or Kubernetes resources. Those permissions
must be granted and tested independently.

## Caller authentication with UAMI

### Proposed Entra setup

Create an Entra application representing agentgateway as a protected API:

```text
audience: api://{{AGENTGATEWAY_APP_ID}}
application roles:
  AgentGateway.Model.Invoke
  AgentGateway.Mcp.Read
  AgentGateway.Mcp.Write         # not issued during the first proof
```

For each application:

1. Create or select a UAMI dedicated to the application or team trust domain.
2. Federate it to exactly:
   `system:serviceaccount:{{TEAM_NAMESPACE}}:{{TEAM_SERVICE_ACCOUNT}}`.
3. Assign only the required agentgateway application roles to that UAMI's
   service principal using Microsoft Graph `appRoleAssignments`.
4. Annotate the ServiceAccount and label the workload pod for AKS Workload
   Identity.
5. Let the application use an Azure Identity SDK to request:
   `api://{{AGENTGATEWAY_APP_ID}}/.default`.
6. Send the token as `Authorization: Bearer <token>` to agentgateway.

Agentgateway must use strict JWT validation and verify at least issuer,
audience, signature, and expiry. Route authorization should use signed claims
such as `roles`, `azp`/application ID, or the managed identity object ID. Do not
use an unsigned `x-team` or `x-agent` header as the identity.

The logical policy is:

```text
authentication:
  issuer == {{ENTRA_TENANT_ISSUER}}
  audience contains api://{{AGENTGATEWAY_APP_ID}}
  mode == Strict

authorization for team route:
  jwt.roles contains AgentGateway.Model.Invoke
  and jwt caller identity is registered to {{TEAM_NAME}}
```

The deployable `AgentgatewayPolicy` shape must be server-side validated against
the installed agentgateway CRD. The repository baseline is v1.3.1, while the
official project continues to evolve.

The managed-identity app-role assignment is not a normal Entra portal action.
The operator must create the service-principal app-role assignment with the
caller principal ID, gateway resource service-principal ID, and app-role ID.
The documented Microsoft Graph application permissions are
`AppRoleAssignment.ReadWrite.All` and `Application.Read.All`; delegated use also
requires a supported Entra administrator role. This is a Phase 1 prerequisite
owned by `{{ENTRA_APPLICATION_ADMIN_OWNER}}`, not an application-team task.

Use [AUTHENTICATION.md](../../../platform/agentgateway/AUTHENTICATION.md) as the repository source for the
JWT/OIDC policy mechanics. This plan defines the ownership and isolation model;
it does not replace that implementation guide.

### Revocation semantics

Removing a managed identity's agentgateway app-role assignment prevents that
role from appearing in subsequently issued tokens after the identity change
propagates. It does not invalidate an already-issued JWT. Because agentgateway
authorises the signed claims embedded in that JWT, a cached role-bearing token
can retain access until its expiry unless gateway policy separately denies the
caller.

Record the maximum accepted token lifetime as the routine-offboarding residual
access window. Test fresh-token issuance separately from reuse of a token issued
before revocation. For immediate incident response, activate an explicit
gateway-side deny keyed to the caller's immutable identity on every applicable
route, then remove the role assignment or grant. Prove that the deny blocks the
already-issued token; do not treat role removal alone as immediate revocation.

### Why the team UAMI should not normally access the model directly

If the team UAMI has direct Model Garden access, it can bypass gateway model
allow-lists, rate limits, prompt controls, cost attribution, and audit policy.
The recommended split is:

```text
team UAMI -> authorised to call agentgateway
gateway UAMI -> authorised to call the model backend
```

Use a distinct backend UAMI when model resources, data classification,
subscriptions, owners, or cost boundaries differ. A shared gateway UAMI is
acceptable only for models inside the same approved trust and policy boundary.

If access must reflect an end user's personal permissions rather than a
workload's permissions, treat that as a separate delegated/on-behalf-of design.
Do not silently forward the caller token to the provider.

## Model access design

First confirm what “Model Garden” means in the target environment:

- Azure OpenAI deployment;
- Azure AI Foundry project/model endpoint; or
- an internal OpenAI-compatible model catalogue.

The required token scope, Azure role, endpoint format, and supported
agentgateway provider differ. The platform must record those details per
backend rather than infer them from the model name.

For each approved model class, publish a platform-owned route with:

- an explicit backend and, where supported, a forced model/deployment;
- strict caller JWT authentication;
- claim-based route authorization;
- request, token, and concurrency controls with their enforcement scope stated;
- maximum request and streaming timeouts;
- data-classification and regional-routing metadata;
- prompt/data controls appropriate to the workload; and
- logs, metrics, traces, model name, caller identity, token usage, and outcome.

Do not rely on the caller-provided `model` field as the authorization boundary.
Prove that an authorised caller cannot select an unapproved deployment through
the same route.

The repository's current `rateLimit.local` examples are per agentgateway
data-plane replica. They are protective throttles, not a fixed cost-centre
budget: the approximate aggregate ceiling is replica count multiplied by the
local limit and changes when autoscaling changes the replica count. A cost
commitment needs a proven global rate-limit service or provider-side quotas and
budget monitoring.

## MCP access design

### Control chain

```text
caller JWT
  -> route authentication and team/capability authorization
  -> AgentgatewayBackend failureMode: FailClosed
  -> MCP authorization by target and exact tool name
  -> gateway-filtered tools/list
  -> denied tools/call outside the grant
  -> MCP server's own least-privilege identity
  -> downstream API/RBAC enforcement
```

Phase 4 must define one versioned source of truth for the approved tool list and
generate the following artefacts from it:

1. the onboarding approval record;
2. agentgateway MCP authorization policy; and
3. kagent Agent `toolNames`, when kagent is the client.

`ToolCatalogEntry` and `ToolGrant` remain proposal-stage controls. The repository
contains proposal CRDs under `infra/byo-kagent/crds/`, bootstrap catalog
manifests under `infra/byo-kagent/bootstrap-catalog/`, and a Kyverno admission
policy example under `infra/byo-kagent/kyverno-policies/`. Those checked-in
artifacts are not evidence that the controls are deployed, compatible with the
target cluster, or runtime-proven, and no controller or renderer is proven.
Until a real source and renderer exist, the platform owner must reconcile the
policy and Agent lists during review. A parity check over hand-maintained lists
is a temporary fallback, not the target control.

The gateway is the runtime tool enforcement point. `toolNames` is useful
client-side narrowing, not a security boundary by itself.

### Tool access is not resource access

Allowing `pods_list` does not necessarily restrict which namespace, cluster,
or subscription can be supplied in that tool's arguments. Do not place a
broad fleet credential behind a team route and assume a tool-name allow-list
makes it namespace-scoped.

Use one of these hard boundaries:

1. Preferred: a team/capability-specific MCP endpoint whose Kubernetes
   ServiceAccount or cloud identity can access only the approved namespace and
   resources.
2. A purpose-built MCP wrapper that validates cluster, namespace, resource,
   and verb before calling the backend.
3. Argument-aware gateway policy only if the installed version exposes the
   required arguments to CEL and live negative tests prove fail-closed
   behaviour.

For the Kubernetes MCP fleet, publish a tenant-safe endpoint or identity rather
than granting application teams the platform-wide fleet reader. Keep AKS-MCP
managed-plane tools platform-only unless a separately reviewed use case
requires them.

### Prevent gateway bypass

- MCP Services are ClusterIP/private and accept ingress only from the
  agentgateway data-plane namespace or identity.
- Tenant NetworkPolicy allows egress to agentgateway, not directly to shared
  MCP Services or model endpoints.
- The MCP server still enforces its own tool configuration and least-privilege
  RBAC.
- Write-capable tools use a separate endpoint and identity, plus an approved
  workflow/HITL boundary.

## Consumer patterns

### Pattern A: ordinary application using an LLM

The application remains team-owned. It obtains a gateway-audience token with
its workload identity and calls the approved OpenAI-compatible route. It does
not need kagent, an Agent CR, or provider credentials.

This should be the first onboarding pattern because caller identity maps
directly to a pod ServiceAccount and UAMI.

### Pattern B: ordinary application using MCP

The application is an MCP client and calls a team-specific Streamable HTTP MCP
route with the same gateway JWT. Agentgateway filters discovery and execution.
The application never receives the backend MCP credential.

### Pattern C: application team creates a kagent Agent

The team creates only the `Agent` resource in its namespace. Platform-owned
`ModelConfig` and `RemoteMCPServer` resources point to approved gateway routes.
Cross-namespace references use the installed kagent `allowedNamespaces`
contract and admission policy.

A shared kagent controller does not automatically give each Agent CR a distinct
workload identity. The gateway may see the controller/runtime identity rather
than the team namespace identity. Before production onboarding, prove one of:

- kagent can attach a short-lived per-agent JWT from a protected source;
- a trusted kagent-side proxy overwrites and signs the agent/team identity;
- each team trust domain has a separate kagent runtime and UAMI; or
- policy intentionally authorises the shared kagent identity, with agent-level
  narrowing treated as defence in depth rather than tenant isolation.

Plain `x-kagent-agent` and `x-kagent-namespace` headers are not sufficient if a
team pod can reach the same gateway route and spoof them.

The Agent's A2A ingress is a separate authentication boundary. Current
repository A2A examples apply routing, timeout, and rate-limit policy but do not
prove caller authentication. Pattern C is not tenant-isolated until A2A ingress
is routed through a strict JWT-authenticated policy, or an equivalent
cryptographic caller boundary is deployed and tested. Network reachability
alone must not let another pod drive an Agent that holds a more privileged
shared kagent gateway grant.

### Pattern D: application team brings an MCP server

Place the server in quarantine first. Inventory its tools, classify each as
read/write/destructive/credential-accessing, inspect its backend identity and
egress, and run allow/deny tests. Promotion creates a versioned approval
record, an explicit authorization policy, a private backend, and a gateway
route. The team does not receive permission to modify shared gateway policy
directly.

## Kubernetes tenancy boundary

The team's namespace Role should allow only the resources it must own. A safe
starting point is:

- normal application Deployments, Services, ConfigMaps, and namespaced
  ServiceAccounts;
- optionally kagent `Agent` resources;
- read-only access to platform-published model/tool references where the CRD
  supports it; and
- no permission to create or modify `AgentgatewayBackend`, shared `HTTPRoute`,
  `AgentgatewayPolicy`, platform `ModelConfig`, platform `RemoteMCPServer`,
  shared credential, or any future tool-catalog/grant resource.

Admission policy should reject:

- direct model-provider URLs;
- direct shared MCP Service URLs;
- wildcard or empty tool lists;
- unapproved cross-namespace references;
- arbitrary `Authorization` header propagation;
- UAMI annotations not assigned to the team;
- host networking, privileged pods, or unrestricted egress; and
- secrets embedded in Agent, ModelConfig, or MCP definitions.

Do not apply the RBAC example in the existing multi-namespace guide unchanged.
It grants tenant management of `ModelConfig` and gateway-related resources,
which is broader than this onboarding boundary. Treat that guide as a topology
reference until its permissions are reconciled with the reviewed design.

## Known gaps in the existing examples

- The current kagent `ModelConfig` examples use a dummy API-key Secret because
  agentgateway owns the provider credential. That satisfies the client schema;
  it does not authenticate the kagent caller to a strict gateway JWT policy.
- A static access token placed in a `ModelConfig` Secret would expire and is not
  an acceptable workload-identity solution. The kagent path needs native token
  acquisition, a trusted identity-aware proxy, or a separately identified
  runtime.
- `x-kagent-*` headers provide useful attribution only after an authenticated
  component sets or overwrites them and untrusted callers cannot reach the
  route directly.
- Repository Azure backend examples are design inputs, not current work-side
  proof. Revalidate native UAMI/Workload Identity fields, pod mutation, token
  scope, Azure role, and refresh behaviour against the installed release.
- Existing shared MCP examples prove tool-name policy. They do not by
  themselves prove namespace, context, subscription, or arbitrary tool-
  argument isolation.
- The repository JWT example resolves Entra signing keys through an
  `oidc-proxy` Service that is not defined in this repository. Strict JWT
  authentication therefore has an unresolved JWKS network, TLS/CA, ownership,
  caching, and signing-key rollover dependency.
- Local rate limits are per data-plane replica and cannot be presented as a
  fixed tenant budget without an additional global or provider-side control.
- Existing A2A examples do not prove authenticated caller-to-Agent ingress.
- Token expiry on established MCP Streamable HTTP sessions and streaming model
  responses has not been measured against the installed version. Clients must
  be designed to refresh and reconnect once the observed contract is recorded.

## Self-service onboarding contract

The team submits a GitOps pull request or a namespaced onboarding request with:

| Field | Required information |
|---|---|
| Ownership | Team, technical owner, support contact, cost centre, expiry/review date |
| Runtime | Application pod, kagent Agent, external client, or team MCP server |
| Identity | Namespace, ServiceAccount, UAMI, Entra application roles requested |
| Model | Provider/catalogue, exact model/deployment, region, data classification, expected rate and token budget |
| MCP | Approval record, exact tools, target namespaces/resources, read/write classification |
| Connectivity | Source cluster/VNet, private DNS/TLS, required egress destinations |
| Data | Prompt/input/output classification, retention, logging/redaction requirements |
| Verification | Allowed request plus authentication, route, tool, RBAC, and network denial tests |

The platform workflow then:

1. validates ownership, identity, model, MCP, data, and cost inputs;
2. checks the UAMI federation subject and gateway app-role assignment;
3. renders platform-owned gateway routes and policies;
4. renders or grants only approved namespaced references;
5. performs server-side CRD validation and policy/admission checks;
6. reconciles through Flux;
7. executes positive and negative smoke tests;
8. publishes a redacted receipt; and
9. records expiry, revocation, and owner review dates.

## Minimum safe proof of concept

Use one application in one development namespace:

- one dedicated caller UAMI;
- one Entra role for a single model route;
- one model deployment with a low quota;
- one read-only namespace-scoped MCP identity;
- one or two harmless MCP tools;
- no platform-wide Kubernetes MCP, AKS-MCP managed-plane tool, write tool, or
  production data.

### Required evidence

| Test | Expected result |
|---|---|
| No bearer token | `401` before backend invocation |
| Invalid or wrong-audience token | `401` |
| Valid UAMI token, approved model | Successful response attributed to team/caller |
| Valid UAMI token, unapproved model route | `403` or route denial |
| Approved MCP `tools/list` | Only granted tools visible |
| Approved MCP tool call | Successful read in the approved namespace |
| Ungranted MCP tool | Hidden from discovery and denied if called directly |
| Same tool, different namespace/resource | Denied by MCP identity/RBAC |
| Direct MCP Service connection | Blocked by network/identity policy |
| Direct model endpoint connection | Blocked or caller UAMI lacks provider role |
| Local rate limit | Deterministic response and metric; observed aggregate matches documented replica-scoped behaviour |
| Fresh-token access after app-role removal | A subsequently issued token has no usable role and the gateway denies access |
| Cached token issued before app-role removal | Residual access lasts until token expiry unless an explicit gateway-side caller deny is active |
| Immediate incident-response revocation | Explicit gateway-side caller deny blocks the already-issued role-bearing token on every applicable route |
| Expired token on a new request | `401` before backend invocation |
| Token expiry on an established MCP or model stream | Deterministic observed outcome recorded; client refresh/reconnect behaviour tested |
| Bearer-token replay from another pod or namespace | Denied by a proven sender/network binding, or recorded as undetectable and mitigated by short token life and network controls |
| Gateway restart or policy reload | Existing denials remain effective with no observed fail-open window |
| Audit record inspection | Caller, route, and decision present; prompts, bearer tokens, credentials, and secrets absent |

Do not call the proof complete from a `Ready` status alone. Retain the caller
identity, route, policy decision, backend/model, tool name, response class,
latency, and token usage without retaining prompts, tokens, or secrets unless
the approved data policy explicitly permits it.

## Showcase meeting structure

The live agenda below is available only after the Phase 1 and Phase 2 exits and
all mandatory evidence rows pass. Until then, book the meeting as a design
review using the front sheet; do not substitute a port-forward, dummy key, open
route, or unscoped MCP for the missing proof.

### Suggested 40-minute agenda

1. Five minutes: what agentgateway provides and what it does not replace.
2. Five minutes: the four-identity authentication boundary.
3. Fifteen minutes: live allow-and-deny demonstration.
4. Ten minutes: application-team onboarding contract and support model.
5. Five minutes: decisions and first proof owner.

### Demonstration story

Use a disposable development caller and read-only backend:

1. Show the same request without a token returning `401`.
2. Obtain a short-lived gateway-audience token using the caller UAMI.
3. Call the one approved model route successfully.
4. Call a second model route and show it is denied.
5. List MCP tools and show only the approved tools.
6. Run one read-only tool successfully.
7. Attempt an ungranted tool and an unapproved namespace and show both denied.
8. Show gateway metrics/logs attributed to the caller and route.
9. Show both revocation paths: a fresh token is denied after app-role removal,
   and an explicit gateway-side caller deny immediately blocks a token issued
   before removal. State that without the gateway deny, the cached token retains
   its embedded role until expiry.

Avoid a demo that relies only on a port-forward, dummy API key, open route, or
prompt instructions saying “read-only”. The security story is the identity and
denial evidence.

## Questions for the App Team

1. Are they bringing an ordinary application, a kagent Agent, another agent
   framework, or an MCP server?
2. Is access workload-to-workload or on behalf of an end user?
3. Which cluster, namespace, ServiceAccount, and UAMI will call the gateway?
4. What exactly is the target “Model Garden” service, model, deployment,
   region, and API contract?
5. What data classification may be sent to the model, and may prompts or
   responses be logged?
6. Which MCP servers and exact tools are needed? Which namespaces, clusters,
   subscriptions, or external systems may those tools access?
7. Are any actions write-capable? If yes, what approval and workflow executor
   owns the mutation?
8. What request rate, concurrency, token budget, timeout, and streaming
   behaviour are expected?
9. What private connectivity, DNS, TLS, and corporate CA path is available?
10. Who owns incident response, access review, cost review, and offboarding?

## Delivery phases

Before implementation, replace every placeholder below and agree target dates.

| Responsibility | Accountable owner | Target date |
|---|---|---|
| Phase 0 installed-contract discovery | `{{PLATFORM_AGENTGATEWAY_OWNER}}` | `{{PHASE_0_TARGET_DATE}}` |
| Entra protected API and app-role assignments | `{{ENTRA_APPLICATION_ADMIN_OWNER}}` | `{{PHASE_1_ENTRA_TARGET_DATE}}` |
| Phase 1 authenticated model route | `{{PLATFORM_AGENTGATEWAY_OWNER}}` | `{{PHASE_1_TARGET_DATE}}` |
| Phase 2 namespace-scoped MCP route | `{{MCP_PLATFORM_OWNER}}` | `{{PHASE_2_TARGET_DATE}}` |
| Phase 3 kagent and authenticated A2A ingress | `{{KAGENT_PLATFORM_OWNER}}` | `{{PHASE_3_TARGET_DATE}}` |
| Phase 4 self-service workflow | `{{PLATFORM_PRODUCT_OWNER}}` | `{{PHASE_4_TARGET_DATE}}` |
| Security evidence approval | `{{SECURITY_APPROVER}}` | `{{SECURITY_REVIEW_TARGET_DATE}}` |

### Phase 0: installed-contract discovery

- Record installed agentgateway, Gateway API, kagent, Istio, and CNI versions.
- Inspect the live CRDs for JWT authentication, HTTP authorization, MCP
  authorization, Azure backend auth, `allowedNamespaces`, and header handling.
- Confirm the model endpoint type, token scope, Azure role, and private network
  path.
- Record the agentgateway replica count and autoscaling behaviour. Classify
  every local limit as per-replica and choose a global/provider-side control if
  a fixed budget is required.
- Resolve the JWKS dependency: name the owner of `oidc-proxy` or its replacement
  path, required Entra egress, private DNS, corporate CA trust, cache duration,
  signing-key rollover behaviour, and alert/metric for retrieval failure.
- Measure token expiry during established MCP Streamable HTTP and streaming
  model responses, and specify client refresh/reconnect behaviour.
- Record the maximum accepted token lifetime, app-role propagation behaviour,
  gateway caller-deny reconciliation time, and routine residual-access window.
- Prove whether the shared kagent runtime can present a trusted per-agent
  identity.

Exit: a version-bound schema and identity decision record. No team access yet.

### Phase 1: authenticated model route

- Create the gateway Entra audience and read-only/invoke application role.
- Federate one development ServiceAccount/UAMI.
- Have `{{ENTRA_APPLICATION_ADMIN_OWNER}}` create and verify the managed-
  identity service-principal app-role assignment through Microsoft Graph.
- Publish one model route with strict JWT authentication, authorization,
  limits, and audit telemetry.
- Prove fresh-token denial after app-role removal, cached-token access until
  expiry, and immediate cached-token denial through the explicit gateway-side
  caller deny.
- Run every model allow/deny test in the evidence table.

Exit: one ordinary application can use one model without provider credentials.

### Phase 2: namespace-scoped MCP route

- Publish one approved read-only MCP endpoint with a narrow backend identity.
- Add fail-closed gateway policy for exact tool names.
- Block direct backend access and prove tool, namespace, and network denials.

Exit: one application can discover and call only its approved MCP capability.

### Phase 3: kagent onboarding

- Decide shared versus per-team kagent identity.
- Put the Agent A2A entry point behind strict caller authentication and prove a
  different namespace cannot drive the Agent as a confused deputy.
- Publish approved ModelConfig and RemoteMCPServer references.
- Restrict tenant Agent authoring with RBAC and admission policy.
- Invoke the Agent through the normal A2A/client path and repeat model/MCP
  denials.

Exit: a namespaced Agent cannot broaden its model or tool permissions.

### Phase 4: repeatable self-service

- Define the onboarding request schema and GitOps workflow.
- Define the real tool-approval resource/schema and generate gateway policy,
  kagent `toolNames`, and approval evidence from that one source of truth.
- Add expiry, routine offboarding, immediate gateway-deny revocation, cost,
  audit, and support runbooks.
- Onboard a second team to prove the process is repeatable.

Exit: onboarding no longer depends on hand-edited shared YAML.

## Review gates and unresolved decisions

Do not implement until reviewers resolve:

- the exact installed agentgateway/kagent versions and accepted CRD fields;
- whether Model Garden means Azure OpenAI, Foundry, or an internal service;
- whether caller identity is workload-level, team-level, agent-level, or
  end-user delegated identity;
- shared gateway backend UAMI versus per-model/per-team UAMI;
- whether MCP policy can safely inspect required arguments in the installed
  release, or separate MCP identities are mandatory;
- the shared-kagent per-Agent identity mechanism;
- private ingress versus same-cluster Service routing;
- data retention, prompt logging, redaction, and audit ownership; and
- who approves write-capable tools and owns the workflow executor.

## Independent review request

Ask the reviewer to challenge these claims specifically:

1. Can any team pod bypass agentgateway and reach a model or MCP directly?
2. Can a valid caller token reach a route, model, MCP target, tool, namespace,
   or cluster outside its grant?
3. Does the downstream MCP identity remain least privilege even if gateway
   policy is removed or wrong?
4. Is kagent caller identity cryptographically trustworthy, or merely a
   spoofable header?
5. Can a team edit any shared ModelConfig, RemoteMCPServer, route, backend,
   policy, grant, or credential?
6. Are authentication, authorization, federation, Kubernetes RBAC, and Azure
   RBAC tested as separate gates?
7. Are routine fresh-token revocation, the cached-token residual window, and
   immediate gateway-side denial tested separately and visible in audit evidence?

## Current evidence classification

Verified upstream capability:

- strict JWT authentication with issuer/audience/JWKS validation;
- CEL authorization using validated JWT claims;
- MCP tool filtering for `tools/list` and enforcement for `tools/call`; and
- Azure backend authentication using workload or managed identity in current
  agentgateway APIs.

Verified repository pattern, but requiring target-version revalidation:

- agentgateway v1.3.1 manifests for model and MCP routes;
- kagent `RemoteMCPServer`, `allowedNamespaces`, `toolNames`, and header
  controls; and
- Kyverno, NetworkPolicy, and GitOps onboarding patterns.

Proposed and not yet proven at work:

- the Entra application-role design for application consumers;
- a trusted per-Agent identity from the shared kagent runtime;
- argument-aware MCP resource scoping;
- the exact Model Garden backend/provider contract;
- the self-service renderer/controller;
- the checked-in `ToolCatalogEntry`/`ToolGrant` CRD, bootstrap-manifest, and
  admission-policy proposal artifacts, which are not deployed or runtime-proven,
  or their replacement; and
- authenticated, tenant-isolated A2A ingress to a kagent Agent.

## References

- [Agent authentication with agentgateway](../../../platform/agentgateway/AUTHENTICATION.md)
- [Agentgateway MCP tool auth and discovery](../../../docs/agentgateway-mcp-tool-auth/README.md)
- [Custom kagent tools](../../../docs/kagent-custom-tools/README.md)
- [Multi-namespace kagent](../../../docs/architecture/MULTI-NAMESPACE-AGENT-AS-A-SERVICE.md)
- [BYO agent boundaries](../../../docs/agentic-delivery-factory/byo-agent-harness-boundaries/README.md)
- [Official agentgateway JWT service authentication](https://agentgateway.dev/docs/kubernetes/main/mcp/mcp-access/)
- [Official agentgateway API reference](https://agentgateway.dev/docs/kubernetes/latest/reference/api/)
- [Official agentgateway MCP tool access](https://agentgateway.dev/docs/kubernetes/main/mcp/tool-access/)
- [AKS Workload Identity configuration](https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster)
- [Microsoft Entra application roles](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps)
- [Managed identity token caching and role changes](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/managed-identities-faq)
- [Microsoft Graph service-principal app-role assignments](https://learn.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignments?view=graph-rest-1.0)
- [Microsoft Foundry REST authentication](https://learn.microsoft.com/en-us/azure/ai-foundry/reference/foundry-project)
