# Customer walkthrough: agentgateway on the agentic cluster

Use this as a 35-minute design-review demonstration. It becomes a live
allow/deny demonstration only after the target environment passes the evidence
checklist.

## 1. What agentgateway is — five minutes

Agentgateway is the governed data-plane entry point between applications or
agents and approved AI/MCP/A2A backends. It uses Gateway API routes and policy
to provide a stable front door while backend identities and endpoints stay
platform-owned.

```text
application
  -> caller authentication and route authorization
  -> agentgateway
       -> LLM routing and backend authentication
       -> MCP discovery/call filtering and backend routing
       -> bounded A2A routing where separately authenticated
       -> rate limits, timeouts, prompt controls and telemetry
```

Agentgateway is not:

- the application's agent loop or chatbot framework;
- the source of Azure/Entra identities or Model Garden entitlements;
- a replacement for MCP backend RBAC or database grants;
- a billing engine;
- proof that every manifest in the repository is deployed; or
- a safe way to expose every MCP tool or A2A Agent to every namespace.

## 2. What the repository currently provides — eight minutes

Open [the capability status](01-CAPABILITY-STATUS.md) and explain the four
evidence states:

1. **Configured** — a checked-in manifest or documented contract exists.
2. **Lab-verified** — a receipt exists for a named version/environment.
3. **Target proof required** — the work environment must validate its installed
   CRDs, identity and network path.
4. **Proposed or blocked** — do not advertise as an available service.

Lead with these facts:

- OpenAI-compatible model routing, policies and monitoring have checked-in
  examples; chat, token metrics and secret rotation were lab-proven on an older
  agentgateway version.
- Strict caller JWT policy is the production target, but the example contains
  an unresolved JWKS/CA/network dependency and is not a deployment receipt.
- PostgreSQL schema discovery is the strongest first MCP candidate because its
  three read-only tools have HomeLab proof.
- GitLab and Kubernetes are catalogue candidates, not automatically approved
  tenant services.
- The Argo OpenAPI-to-MCP example is explicitly blocked by the inspected CRD.
- A2A routing has a data-path proof, but tenant identity is not enforced by the
  checked gateway policy; kagent onboarding therefore needs the Phase 3 proof.

## 3. Explain the identity split — five minutes

```text
team workload identity
  -> requests an agentgateway-audience token
  -> may call only assigned gateway routes

agentgateway backend identity
  -> requests the Model Garden audience token
  -> may invoke only the approved provider resource

MCP backend identity
  -> accesses only approved data/resources
```

The Model Garden team owns its endpoint, audience/scope, entitlement, quota and
billing. The platform gives them the gateway backend UAMI or service-principal
identity to authorize. Prefer Workload Identity/UAMI token acquisition; do not
pass the application token through to the provider.

## 4. Onboard the dummy application — ten minutes

Open [the worked scenario](scenarios/01-llm-postgres-mcp.md) and present the
completed request as if the customer supplied it.

The platform decision is intentionally narrow:

- one namespace and ServiceAccount;
- one caller UAMI and one gateway application role;
- one approved model route;
- one PostgreSQL MCP endpoint;
- exactly `list_schemas`, `list_tables` and `describe_table`;
- no row queries, SQL, writes or cross-namespace access; and
- metadata-only gateway telemetry.

Explain that the application makes two independently authorized calls: an
OpenAI-compatible model call and an MCP Streamable HTTP call. Its own agent loop
decides when to call a tool and how to return the result to the model.

## 5. Show how acceptance works — five minutes

Use [the evidence checklist](evidence/ACCEPTANCE-CHECKLIST.md). The headline
proof is not “the application returned an answer.” It is the full matrix:

- valid caller, approved model and approved MCP tool succeed;
- missing/wrong token, wrong route and unapproved tool fail;
- the same tool cannot exceed the MCP backend's data boundary;
- direct model and MCP bypass are blocked;
- restart/policy reload does not create a fail-open window; and
- audit data contains identity/route/tool/outcome without tokens, credentials
  or prompt content.

## 6. Close with decisions — two minutes

Ask the customer to confirm:

1. named application, owner, namespace and cost owner;
2. existing versus platform-created ServiceAccount/UAMI;
3. exact Model Garden service contract;
4. exact MCP server and tool names;
5. data classification and logging rules;
6. expected rate, timeout and streaming behaviour; and
7. support, expiry and revocation owners.

If any answer is unknown, record it as an owned Phase 0 dependency. Do not fill
it with an architectural assumption and call the application onboarded.
