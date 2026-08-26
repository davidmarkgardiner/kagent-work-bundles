# Agentgateway application onboarding work bundle

Status: customer walkthrough and onboarding-mechanism proof. This bundle does
not deploy an application, grant Azure access, or claim that proposal manifests
are active in a target cluster.

## Purpose

Use this one folder to:

- explain what agentgateway provides on the agentic cluster;
- distinguish checked-in configuration, lab evidence, target-cluster proof and
  future proposals;
- interview an application team consistently;
- onboard a dummy application that needs an LLM and one approved read-only MCP
  capability; and
- leave a repeatable request and acceptance-evidence contract for the next
  application.

The standard path assumes the application runs in its own namespace on the
agentic cluster. An external cluster or non-Kubernetes caller is an exception
lane with separate ingress, network and identity discovery.

## Start here

1. Present [the customer walkthrough](00-CUSTOMER-WALKTHROUGH.md).
2. Use [the capability status](01-CAPABILITY-STATUS.md) to answer “what is
   already configured?” without turning repository YAML into a deployment
   claim.
3. Show the [platform MCP catalogue](02-PLATFORM-MCP-CATALOG.md).
4. Run the [customer interview](03-CUSTOMER-INTERVIEW.md).
5. Walk through the completed
   [LLM plus PostgreSQL MCP scenario](scenarios/01-llm-postgres-mcp.md).
6. Compare its [completed request](records/demo-llm-postgres-request.yaml) with
   the reusable [request template](templates/application-onboarding-request.yaml).
7. Agree who will collect the [acceptance evidence](evidence/ACCEPTANCE-CHECKLIST.md).

## First proof-of-concept posture

```text
demo application in team namespace
  -> team ServiceAccount and federated caller UAMI
  -> short-lived token for the agentgateway audience
  -> agentgateway
       -> approved Model Garden route
          -> gateway backend UAMI obtains the provider token
       -> approved PostgreSQL MCP route
          -> only list_schemas, list_tables and describe_table
          -> MCP identity/database grants remain the data boundary
```

The application must already be capable of an OpenAI-compatible model call and
MCP Streamable HTTP. Agentgateway is the routing and policy plane; it is not the
application's agent/tool loop.

## Onboarding lanes

| Lane | Initial status | Meaning |
|---|---|---|
| Application and model route | Required | Namespace, workload identity, gateway role, approved model route and telemetry |
| Platform MCP attachment | Optional | Select a platform-reviewed MCP server and exact tool names |
| Bring-your-own kagent Agent | Later scenario | Requires authenticated A2A ingress and a proven kagent caller-identity model |
| Bring-your-own MCP server | Separate workflow | Requires provenance, tool, credential, egress and resource-scope review |

## Folder map

| Path | Purpose |
|---|---|
| `00-CUSTOMER-WALKTHROUGH.md` | Meeting script and demo sequence |
| `01-CAPABILITY-STATUS.md` | Honest configured/proven/proposed inventory |
| `02-PLATFORM-MCP-CATALOG.md` | MCP choices and promotion criteria |
| `03-CUSTOMER-INTERVIEW.md` | Reusable discovery questionnaire |
| `scenarios/` | Worked onboarding cases |
| `templates/` | Blank onboarding request contract |
| `records/` | Completed sanitized example request |
| `evidence/` | Allow, deny and ownership acceptance checklist |
| `reference/` | Full front sheet, design record and independent review |

## Ownership boundary

| Owner | Responsibility |
|---|---|
| Application team | Application, namespace workload, client token refresh, agent/tool loop and declared data use |
| Agentic-platform team | Gateway listener, routes, caller authorization, MCP catalogue attachment, network controls and gateway telemetry |
| Model Garden team | Provider endpoint, token audience/scope, accepted backend identity, model entitlement, quotas and billing |
| MCP/data owner | MCP workload identity, backend permissions, approved tools/resources and data classification |

The Model Garden bill remains owned by the Model Garden service. Gateway usage
telemetry is reconciliation evidence, not the billing system of record.

## Definition of done for this documentation proof

- The customer can explain the two identity hops: caller to gateway and gateway
  to backend.
- Every advertised capability has an evidence status.
- One dummy request reaches an owner-approved decision for a model and exact
  MCP tools.
- Required positive and negative evidence is assigned to an owner.
- BYO MCP and write-capable tools remain outside the first proof.
- No secret, private endpoint, tenant ID, subscription ID or real token appears
  in the bundle.
