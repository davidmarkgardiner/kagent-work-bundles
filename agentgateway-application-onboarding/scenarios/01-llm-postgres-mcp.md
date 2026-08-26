# Worked scenario: dummy application with LLM and PostgreSQL MCP

Status: accepted as a documentation proof; target deployment and live access
remain unperformed.

## Customer statement

> We are onboarding `demo-support-assistant` to the agentic cluster. It needs
> one approved Model Garden chat route and read-only PostgreSQL schema metadata
> so it can explain which approved tables exist. It must not query rows,
> generate or execute SQL, modify data, or reach an MCP Service directly.

## Assumptions supplied for the demonstration

| Question | Demonstration answer |
|---|---|
| Application owner | `{{APPLICATION_OWNER}}` |
| Platform owner | `{{PLATFORM_AGENTGATEWAY_OWNER}}` |
| Model provider owner | `{{MODEL_GARDEN_OWNER}}` |
| MCP/data owner | `{{POSTGRES_DATA_OWNER}}` |
| Namespace | `team-demo` |
| Workload | Existing application with OpenAI-compatible and MCP Streamable HTTP clients plus a tool loop |
| Caller identity | ServiceAccount `demo-support-assistant`; dedicated UAMI federated only to that subject |
| User identity | Workload-to-workload for the first proof; no delegated end-user authorization |
| Model route | One provider-forced chat route supplied after Model Garden contract discovery |
| Backend model identity | Dedicated agentgateway backend UAMI authorized by the Model Garden team |
| Billing | Model Garden is system of record; gateway emits reconciliation metadata |
| MCP | PostgreSQL schema discovery through agentgateway |
| Tools | `list_schemas`, `list_tables`, `describe_table` |
| Data | Schema/table/column metadata only; no rows or unrestricted SQL |
| Telemetry | Caller, route, model, token count, tool name, outcome and latency; no bearer token, credential, prompt or tool result |
| Expiry | `{{ACCESS_REVIEW_DATE}}` |

## Request flow

```text
demo-support-assistant pod
  -> acquire api://{{AGENTGATEWAY_APP_ID}}/.default as caller UAMI
  -> model call to approved gateway route
       -> agentgateway route/claim policy
       -> backend UAMI token for {{MODEL_GARDEN_AUDIENCE}}
       -> Model Garden endpoint
  -> MCP call to /mcp/postgres-inventory
       -> agentgateway exact-tool policy
       -> MCPg schema-only tools
       -> dedicated PostgreSQL metadata reader/database grants
```

These are two gateway calls. Agentgateway does not decide when the application
should call an MCP tool; the application's agent loop owns that decision.

## Platform onboarding decisions

1. Create or approve namespace `team-demo` and ServiceAccount
   `demo-support-assistant` through the platform GitOps path.
2. Federate exactly that ServiceAccount subject to the caller UAMI.
3. Assign only the gateway application role for the approved model and MCP
   routes. Managed-identity app-role assignment is owned by
   `{{ENTRA_APPLICATION_ADMIN_OWNER}}`.
4. Publish a provider-forced model route after the Model Garden team confirms
   endpoint, API shape, audience/scope, model and backend identity.
5. Attach the PostgreSQL MCP route `/mcp/postgres-inventory` with exactly the
   three schema tools.
6. Keep the MCP credential inside the MCP workload. Keep the Model Garden
   credential/token acquisition inside agentgateway.
7. Block application access to the Model Garden endpoint and PostgreSQL MCP
   Service except through approved platform paths.
8. Record metadata-only telemetry and an expiry/review date.

## Explicit denials

- No token or wrong-audience token to agentgateway.
- Any model route or model deployment outside the application grant.
- MCP tools other than `list_schemas`, `list_tables` and `describe_table`.
- `run_select`, arbitrary SQL, row access and all writes.
- Direct connection from the application namespace to the MCP Service.
- Direct model-provider access using the caller UAMI.
- Cross-namespace or alternative database target supplied as a tool argument.

## Phase 0 dependencies

- Installed agentgateway and policy CRD fields server-validated.
- Real strict-JWT JWKS path, DNS, egress, corporate CA, cache and rollover
  behaviour agreed.
- Model Garden endpoint, audience/scope, model and backend UAMI acceptance
  supplied by its owner.
- Application client obtains and refreshes the gateway-audience token.
- PostgreSQL work overlay, image, private endpoint, Secret delivery and reader
  grants validated by the data owner.
- NetworkPolicy/Istio behaviour proven for the target CNI and mesh.

## Proof sequence

1. Prove the Model Garden backend from agentgateway with its backend identity.
2. Prove missing, invalid and wrong-audience caller tokens fail before backend
   invocation.
3. Prove the caller token succeeds only on the approved model route.
4. Prove direct MCP discovery, then gateway MCP discovery, before involving the
   application.
5. Prove the gateway returns only the three approved tools.
6. Run `list_schemas` or `describe_table` and retain a redacted receipt.
7. Attempt an unapproved MCP tool and an out-of-scope resource; both must fail.
8. Block the direct MCP probe and prove only the gateway route remains.
9. Restart/reload gateway policy and repeat a denial to detect fail-open
   behaviour.
10. Inspect audit/metrics for identity, route, tool and outcome without content
    or credentials.

The completed machine-readable record is
[`../records/demo-llm-postgres-request.yaml`](../records/demo-llm-postgres-request.yaml).
