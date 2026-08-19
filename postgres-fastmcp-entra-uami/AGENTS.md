# FastMCP dual-authentication bundle boundary

This directory contains one FastMCP tool implementation with two PostgreSQL
authentication deployments.

- Use `adapter/` and this directory's `README.md` as the complete work handoff.
- `password/` is the initial username/password Secret path.
- The root Kustomize target is the later AKS Workload Identity -> UAMI ->
  Microsoft Entra token path.
- Both paths must expose exactly the same FastMCP tools and approved queries.
- Passwords must come only from `secretKeyRef`; never put a password or
  connection string in Git, values files, ConfigMaps, logs, or evidence.
- Never add MCPg manifests to this bundle.
- Do not copy deployable files from `../postgres-mcpg-password/`.

The evidence directory is historical and sanitized. It is not deployment input.
