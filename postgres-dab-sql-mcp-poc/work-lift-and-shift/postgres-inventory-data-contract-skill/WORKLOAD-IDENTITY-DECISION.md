# MCPg and Azure workload identity decision

Status: **MCPg direct passwordless database authentication is not supported by
this work bundle and requires validation upstream.**

## Decision

Do not attempt to make MCPg v0.7.1 use AKS workload identity by putting an
Entra access token into `MCPG_DATABASE_URL`. The token is short-lived and MCPg
is configured with a static DSN; this bundle has no verified token-acquisition
or pool-refresh mechanism.

`MCPG_AUTH_MODE=oidc` is not a PostgreSQL authentication feature. It validates
callers to MCPg's HTTP endpoint. It does not cause MCPg to obtain an Entra
token or authenticate its PostgreSQL connection as the AKS workload identity.
This follows the [MCPg v0.7.1 configuration model](https://github.com/devopam/MCPg/blob/v0.7.1/README.md),
which requires `MCPG_DATABASE_URL` for the PostgreSQL connection.

| Requirement | MCPg v0.7.1 | Recommended path |
|---|---|---|
| Password/Secret-backed PostgreSQL reader | Supported by the current bundle | MCPg with a TLS DSN and SELECT-only role |
| MCP HTTP caller authentication | Supported separately through MCPg OIDC or Agent Gateway | Agent Gateway policy and work identity design |
| AKS UAMI / workload identity to Azure PostgreSQL via Entra token | **Not verified or configured by MCPg** | Small custom FastMCP adapter using Azure Identity and psycopg3 |

## FastMCP target shape

```text
kagent Agent
  -> Agent Gateway allowlist
  -> custom FastMCP adapter Pod
  -> DefaultAzureCredential / AKS workload identity
  -> short-lived Entra token
  -> Azure Database for PostgreSQL Flexible Server
```

The adapter should use the Microsoft-supported Azure PostgreSQL auth library
with psycopg3, acquire `https://ossrdbms-aad.database.windows.net/.default`,
and create/refresh database connections through that library. It should expose
typed, owner-approved functions or a very narrow read-query function; it must
not become a generic SQL or credential proxy.

Microsoft documents the required
[Azure PostgreSQL auth library](https://learn.microsoft.com/en-us/python/api/overview/azure/postgresql-auth-readme?view=azure-python)
and the database-side [managed-identity connection model](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/security-connect-with-managed-identity).

## Preconditions for a FastMCP proof

1. Azure Database for PostgreSQL Flexible Server has Microsoft Entra
   authentication enabled.
2. The database owner creates an Entra-mapped PostgreSQL principal for the
   UAMI and grants only `CONNECT`, schema `USAGE`, and `SELECT` on approved
   views.
3. AKS workload identity is enabled; the adapter's Kubernetes ServiceAccount
   is federated to the UAMI and its Pod carries the required workload-identity
   label/annotation.
4. Private DNS, private endpoint/network path, TLS validation, and egress from
   the adapter namespace are verified.
5. The owner approves the views, columns, joins, classification, and initial
   query catalogue.

## Verification gates

1. From the adapter Pod, acquire an Entra PostgreSQL access token without a
   database password Secret.
2. Connect to the PostgreSQL endpoint with TLS and execute `SELECT 1`.
3. Prove a SELECT from an approved view; prove denial for a base table and for
   a write statement.
4. Wait past a token refresh boundary or force a new pooled connection and
   repeat the approved query.
5. Route the adapter through Agent Gateway, mount it to kagent, and retain the
   A2A receipt plus the negative-test evidence.

Until all five gates pass, the current MCPg profile is suitable only for the
password/Secret-backed proof path, not a passwordless work deployment.
