# FastMCP + PostgreSQL bounded-tools POC — re-verification

Date: 2026-08-14

Cluster: `red` HomeLab
Data: synthetic Kubernetes namespace and container-image inventory only

## Verdict

**PASS — custom FastMCP can expose typed, read-only PostgreSQL functions to a
kagent Agent without giving the Agent arbitrary SQL or a database credential.**

## Implementation under test

The POC service is defined in
[postgres-adapter.yaml](../postgres-adapter.yaml). It uses `FastMCP` and
`psycopg`, runs Streamable HTTP at `/mcp`, and exposes exactly four functions:

```text
get_kubernetes_inventory_data_product_details
get_namespace_workload_summary(namespace_name)
get_namespace_container_images(namespace_name, limit)
get_image_risk_summary(namespace_name, severity_min)
```

The two query functions receiving user-derived values use PostgreSQL parameter
binding (`%s` with a parameter tuple). The severity predicate is selected from
two fixed strings only; it does not interpolate user SQL. The adapter has the
connection Secret, while the kagent Agent has only a `RemoteMCPServer` binding
and the four explicit tool names.

The HomeLab image installs `fastmcp==2.14.3` at container startup. That is an
intentional lab convenience, not a production image pattern. Build, scan,
sign, mirror, and digest-pin a custom image before any office deployment.

## Live checks run

```sh
sh work-agent-bundles/postgres-dab-sql-mcp-poc/scripts/verify.sh red
```

The live verifier exited `0` and emitted all required markers:

```text
POSTGRES_SEED_JOB_COMPLETED_OK
PGVECTOR_EXTENSION_AND_INDEX_OK
POSTGRES_SYNTHETIC_KUBERNETES_QUERY_OK namespace=payments count=2
REMOTE_MCP_DISCOVERY_OK
KAGENT_AGENT_READY_OK
A2A_PARAMETERISED_TOOL_CALLS_OK
A2A_CONVERSATIONAL_RESPONSE_OK
VERIFY_PASS
```

It confirmed:

| Layer | Result |
|---|---|
| PostgreSQL 17 + pgvector fixture | Seeded; `vector` extension and HNSW index present. |
| FastMCP service | Deployment Ready; Streamable HTTP MCP reachable by kagent. |
| kagent `RemoteMCPServer` | `Accepted=True`; discovered exactly the four typed tools above. |
| kagent Agent | `Accepted=True`, `Ready=True`; bound only to those four tools. |
| Conversational call | Passed; model first called metadata then the typed risk-summary tool. |

## Fresh A2A receipt

A second fresh request asked which `payments` container images had high or
critical findings. The Agent returned the required
`FASTMCP_POSTGRES_REPLY_OK` marker and reported two synthetic rows:

| Workload | Image | High | Critical |
|---|---|---:|---:|
| `payments-api` | `registry.example.invalid/payments-api:2.4.1` | 2 | 0 |
| `payments-worker` | `registry.example.invalid/payments-worker:1.9.0` | 3 | 1 |

The protocol history records successful calls to
`get_kubernetes_inventory_data_product_details` and
`get_image_risk_summary`; neither function response was an error. The trimmed,
synthetic-only receipt is checked in at
[FASTMCP-KUBERNETES-INVENTORY-A2A-RECEIPT-2026-08-14.json](FASTMCP-KUBERNETES-INVENTORY-A2A-RECEIPT-2026-08-14.json).

## Boundaries not proven

- Azure PostgreSQL, private endpoint/DNS, or the work database schema;
- Microsoft Entra/UAMI/AKS Workload Identity database authentication;
- Agent Gateway as the enforced MCP route or its work-release policy schema;
- real data classification, masking, tenancy rules, or model-egress approval;
- a production image, CI supply-chain checks, monitoring, or availability
  design.

## Next practical step

Replace the synthetic view queries with owner-approved views and a first set of
four or five parameterised questions. Keep the FastMCP tool contract narrow;
add a tool only when its inputs, result shape, data classification, database
grant, and negative tests are agreed.
