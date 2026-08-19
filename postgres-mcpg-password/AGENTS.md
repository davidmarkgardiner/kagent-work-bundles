# Standalone MCPg password/Secret bundle boundary

This directory is the **MCPg v0.7.1 username/password path only**.

- Authentication is a dedicated PostgreSQL reader delivered through the
  approved Secret system as `MCPG_DATABASE_URL`.
- Never add FastMCP, Azure Identity, UAMI client/object IDs, workload-identity
  annotations, or Entra principal SQL to this bundle.
- Do not copy deployable files from `../postgres-fastmcp-entra-uami/`.
- If the requested design requires AKS Workload Identity/UAMI, stop and use the
  separate sibling FastMCP bundle instead.

Historical files elsewhere in the parent POC are not part of this work bundle.
