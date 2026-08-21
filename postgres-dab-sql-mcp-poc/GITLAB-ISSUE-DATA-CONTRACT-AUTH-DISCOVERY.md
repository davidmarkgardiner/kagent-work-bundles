# Proposed GitLab issue: define the governed data MCP contract and authentication path

**Suggested title:** Design discovery: governed PostgreSQL / data-mesh MCP contract for kagent

**Suggested labels:** `architecture`, `data-platform`, `postgresql`, `kubernetes`, `ai-agent`, `mcp`, `poc`

## Purpose

We need an agreed, governed way for a kagent agent to answer a small set of
business or operational questions from the data platform. This issue is a
joint discovery/design exercise. It does **not** authorise production data
access, write operations, credential sharing, or a production deployment.

The core decision is not whether an LLM can create SQL. It is which approved
MCP functions should exist, their typed inputs and returned fields, and the
identity/network/audit boundary that makes each call safe.

## What Platform has already proven

### Verified current capability — kagent/MCP integration

In HomeLab, kagent successfully mounted a `RemoteMCPServer` with an explicit
two-function allowlist. A conversational A2A task called both functions,
received successful responses, and returned the correct synthetic answer.

```text
conversational request
  -> kagent Agent (no database credential)
  -> RemoteMCPServer explicit function allowlist
  -> bounded, read-only MCP service
  -> PostgreSQL + pgvector synthetic data
  -> redacted conversational result
```

The demonstrated functions were:

| Function | Purpose | Inputs | Result |
|---|---|---|---|
| `get_kubernetes_inventory_data_product_details` | Retrieve the approved product contract | none | Product scope, fields, controls |
| `get_image_risk_summary` | Return bounded synthetic image-risk rows | `namespace_name`, `severity_min` | Count and safe summary rows |

Live evidence: [PostgreSQL/pgvector POC README]({{REPO_URL}}/work-agent-bundles/postgres-dab-sql-mcp-poc/README.md), [run record]({{REPO_URL}}/work-agent-bundles/postgres-dab-sql-mcp-poc/evidence/POC-RUN-2026-08-12.md), and [trimmed A2A receipt]({{REPO_URL}}/work-agent-bundles/postgres-dab-sql-mcp-poc/evidence/A2A-CONVERSATIONAL-RECEIPT-2026-08-12.json).

For a side-by-side explanation of AKS-MCP, GitHub MCP, and this bounded data
MCP pattern, see [MCP tool grouping comparison]({{REPO_URL}}/work-agent-bundles/postgres-dab-sql-mcp-poc/MCP-TOOL-GROUPING-COMPARISON.md).

### Verified current capability — boundary

The Agent did not receive arbitrary SQL, database credentials, write tools,
raw-table access, or vector-search access. The MCP service used a dedicated
read-only identity and queried a curated view only.

### Unknown / requires validation — target estate

We do not yet know the actual data product, schema, semantic layer, endpoint,
existing MCP/API, authentication method, audit facilities, or network route in
the target environment. Do not infer any of these from the HomeLab proof.

## Questions to answer in this issue

### 1. Data contract

Please provide or agree the smallest non-production synthetic/masked data
product suitable for the POC:

| Contract item | Required answer |
|---|---|
| Business questions | Four or five high-value questions an operator needs answered |
| Product owner | Named data owner accountable for fields, definitions, and approval |
| Source | Azure Database for PostgreSQL, Starburst/data mesh, semantic layer, or another Azure service |
| Safe interface | Curated view, stored procedure, parameterised query, API, or existing MCP function |
| Allowed fields | Exact output columns, classification, masking/redaction rules |
| Inputs | Typed parameters, required/optional status, allowed values/ranges, maximum date window |
| Limits | Row cap, timeout, rate/cost guardrails, pagination behaviour |
| Freshness | Expected refresh cadence and how stale/partial data is indicated |
| Audit | Query/correlation ID, actor identity, tool name, request/response retention |
| Deny behaviour | Out-of-scope product/field/parameter response and evidence |

### 2. Existing functions or tools

Please identify whether any of the following already exist and are approved:

- an MCP server/function catalogue;
- a Starburst native MCP endpoint, semantic-layer API, or governed query API;
- PostgreSQL views, stored procedures, or parameterised queries that already
  represent the desired questions;
- a data-product catalogue/metadata API; and
- a standard audit/query-history endpoint.

If an approved tool exists, Platform will integrate it rather than create a
replacement. If it does not, the preferred fallback is a small MCP service
that exposes only agreed named functions backed by read-only curated views.

### 3. Initial candidate functions/queries

These are proposals, not assumptions about current tables or fields. Data
owners should rename, replace, or reject them.

| Candidate function | Typed inputs | Intended result | Guardrails |
|---|---|---|---|
| `get_data_product_details` | `product_id` | Approved description, fields, freshness, permitted query functions | Metadata only |
| `get_open_exceptions_summary` | `severity_min`, `from_date`, `to_date`, `limit` | Count by severity/status; optional masked examples | Fixed max date range and row limit |
| `get_control_compliance_summary` | `control_family`, `as_of_date` | Compliant/non-compliant/unknown counts and freshness | Enumerated control family only |
| `get_service_risk_summary` | `service_id`, `from_date`, `to_date` | Aggregate risk/trend indicators | Authorised service IDs only |
| `get_exception_trend` | `group_by`, `from_date`, `to_date` | Bounded time-series aggregates | `group_by` enum; no free-form expression |

Each function should map to one approved query/view/procedure. Do **not**
expose a general `execute_sql(query)` capability for the first POC.

### 4. Authentication and network design

Separate the three distinct boundaries below; they are not interchangeable.

| Boundary | Proposed responsibility | Decision required |
|---|---|---|
| Agent -> MCP | kagent binds only explicit functions; Agent Gateway may provide MCP routing, policy, authentication, and telemetry | Is Agent Gateway required for this endpoint and which client authentication does it enforce? |
| MCP workload -> secret/identity provider | Kubernetes service account/workload identity retrieves a short-lived credential or token | Which identity issuer and secret/token delivery mechanism is approved? |
| MCP workload -> data service | The MCP service authenticates as a dedicated, least-privilege non-human database/data-product identity | Which database/data-mesh authentication method, role grants, TLS, and private network path are supported? |

#### Important authentication clarification

For Azure Database for PostgreSQL Flexible Server, the preferred path to
validate is: an AKS service account federates to a user-assigned managed
identity through AKS Workload Identity; the MCP service obtains a Microsoft
Entra access token; Azure PostgreSQL maps that identity to a dedicated
read-only PostgreSQL role; and the service passes the short-lived token when
opening its TLS connection. The Agent never receives that token.

The fallback is a dedicated read-only database user delivered and rotated only
for the MCP workload through the approved secret mechanism. A third option is
an existing authenticated Starburst/data-mesh endpoint, in which case the MCP
service authenticates to that approved endpoint rather than directly to
PostgreSQL.

Agent Gateway can be valuable for the agent-to-MCP boundary, but it does not
replace the database/data-mesh authentication and role grants unless it is
deliberately configured as that authenticated proxy.

Microsoft documents AKS Workload Identity as a pod-to-Microsoft Entra identity
mechanism: [AKS Workload Identity overview](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview). Azure Database for PostgreSQL Flexible Server
supports Microsoft Entra authentication for managed identities and maps those
identities to PostgreSQL roles: [managed identity connection guidance](https://learn.microsoft.com/en-us/azure/postgresql/security/security-connect-with-managed-identity).

## Proposed POC completion criteria

We can call the first data-access POC complete when all of the following are
evidenced against non-production synthetic or masked data:

- [ ] One approved data contract is completed and signed off by its data owner.
- [ ] Four or five named, read-only functions are agreed, each with typed
  inputs, result schema, limits, and owner-approved backing query/interface.
- [ ] The preferred existing MCP/API is selected, or the bounded adapter is
  explicitly approved as the temporary implementation.
- [ ] One dedicated non-human read-only identity and private TLS network route
  work end-to-end; no database credential is mounted in the kagent Agent.
- [ ] kagent discovers only the approved functions and the Agent allowlist
  matches exactly.
- [ ] Each of the four or five representative questions returns an expected,
  redacted result and an auditable correlation/query reference.
- [ ] One denied request proves that an unapproved product, field, parameter,
  or write action cannot be accessed.
- [ ] Image provenance, credential rotation, audit retention, cleanup, and
  handover ownership are recorded.

## Requested outcome from this discussion

Please respond with:

1. the candidate non-production data product and owner;
2. the actual schema/semantic contract and initial questions;
3. any existing MCP/API/query tools that should be reused;
4. the supported authentication and private-network approach; and
5. confirmation of the preferred four-to-five-function POC scope.

Platform will then convert the agreed contract into a small, reviewable,
evidence-first deployment and test plan. No implementation against target data
begins until those decisions are recorded.
