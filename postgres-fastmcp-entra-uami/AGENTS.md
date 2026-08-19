# FastMCP Entra/UAMI bundle boundary

This directory is the **passwordless FastMCP path only**.

- Use `adapter/` and this directory's `README.md` as the complete work handoff.
- Authentication is AKS Workload Identity -> UAMI -> Microsoft Entra token.
- Never add `MCPG_DATABASE_URL`, `POSTGRES_PASSWORD`, `PGPASSWORD`, a database
  connection-string Secret, or MCPg manifests to this bundle.
- Do not copy deployable files from `../postgres-mcpg-password/`.
- If the requested design uses a username/password or DSN Secret, stop and use
  the separate MCPg bundle instead.

The evidence directory is historical and sanitized. It is not deployment input.
