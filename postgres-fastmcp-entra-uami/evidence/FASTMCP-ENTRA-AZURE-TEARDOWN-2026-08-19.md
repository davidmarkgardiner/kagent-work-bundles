# FastMCP Entra/UAMI bundle — Azure teardown receipt

Date: 2026-08-19
Scope: cloud resources used by the live FastMCP/PostgreSQL proof

## Result

**PASS — the cost-bearing Azure POC resources were deleted after evidence was
captured.**

## Confirmed deletion

- Azure Kubernetes Service cluster count: `0`
- Azure Database for PostgreSQL Flexible Server count: `0`
- AKS-managed `MC_` resource-group count: `0`
- ACR repository `platform/fastmcp-postgres-entra`: absent
- FastMCP ServiceAccount federated-identity credential: deleted
- Temporary local kubeconfig and image-digest files: deleted

Deleting the PostgreSQL server also removed the three-row synthetic fixture,
the mapped PostgreSQL UAMI role, and the duplicate temporary human Entra
administrator entries described in the live evidence record. Deleting AKS
removed the FastMCP Deployment, Service, ServiceAccount, namespace, and managed
cluster resources.

The existing Azure Container Registry was not created by this proof and was
left intact. Only the POC repository, which contained one recovery tag, was
removed. The existing user-assigned managed identity was also retained; the
cluster-specific federated credential was removed. Neither retained object was
created during this teardown turn.

## Evidence boundary

The cloud runtime is intentionally no longer available for re-query. The
sanitized proof remains in
[FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md](FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md),
and the repeatable work procedure remains in this bundle's
[`README.md`](../README.md).
