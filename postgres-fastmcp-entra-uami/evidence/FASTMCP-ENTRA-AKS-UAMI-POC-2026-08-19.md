# FastMCP PostgreSQL Entra/UAMI bundle — AKS live evidence

Date: 2026-08-19
Scope: authorized Azure POC resources; synthetic data only

## Verdict

**PASS — FastMCP is deployed on AKS and connects to Azure Database for
PostgreSQL using AKS Workload Identity and a non-admin UAMI.**

The target cluster does not currently have the kagent and Agent Gateway CRDs,
so this record proves the direct MCP service and PostgreSQL identity boundary,
not the final kagent/Agent Gateway/A2A path.

## Durable runtime evidence

- The image was built in the sole accessible Azure Container Registry and the
  Deployment uses its resolved digest, not a mutable tag.
- The Deployment rolled out successfully in namespace `fastmcp-entra-poc`.
- The existing federated UAMI acquired an Azure PostgreSQL access token from
  the Pod without a password or database connection-string Secret.
- DNS and TCP/5432 from the Pod to PostgreSQL succeeded.
- TLS `SELECT 1` succeeded through `EntraConnection`.
- `SELECT` from `public.approved_namespace_inventory` succeeded.
- The UAMI cannot `SELECT` the base table and has no `INSERT`, `UPDATE`, or
  `DELETE` privileges on the approved view.
- A fresh Entra-authenticated connection succeeded.
- A network MCP client called the running Kubernetes Service, discovered
  exactly three bounded tools, invoked `get_namespace_count`, and received `3`.

The database contains only a three-row synthetic namespace fixture created for
this proof. It is not production inventory.

## Markers observed

```text
ENTRA_TOKEN_ACQUISITION_OK
POSTGRES_TLS_SELECT_ONE_OK
APPROVED_VIEW_SELECT_OK
BASE_TABLE_SELECT_DENIED_OK
APPROVED_VIEW_WRITE_DENIED_OK
FRESH_ENTRA_CONNECTION_OK
FASTMCP_ENTRA_DATABASE_GATES_PASS
```

## Remaining work and cleanup caveat

1. Install or target an approved kagent/Agent Gateway environment, apply the
   checked-in Gateway template, and retain an A2A receipt.
2. Replace the synthetic view contract with the data-owner-approved work view.
3. Move PostgreSQL from public network access to the approved private-network
   design before treating this as a work deployment.
4. During the live run, two duplicate temporary Entra administrator entries for
   the signed-in human bootstrap identity remained reported by Azure despite
   delete requests. The PostgreSQL server was subsequently deleted in full, so
   those server-scoped entries no longer exist. See the
   [teardown receipt](FASTMCP-ENTRA-AZURE-TEARDOWN-2026-08-19.md).

## Post-proof state

The AKS cluster, PostgreSQL server, POC ACR repository, and cluster-specific
FastMCP federated credential were deleted after this evidence was captured.
This file is a historical sanitized receipt, not a claim that the runtime is
still available.
