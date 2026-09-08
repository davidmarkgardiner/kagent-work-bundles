# Legacy SQL-tool policy

Use this only when the installed MCP exposes an owner-approved SQL-text tool.
Typed FastMCP operations remain the preferred path.

The server must parse PostgreSQL SQL into an AST. Regex or prompt instructions
are not enforcement. Apply these rules before execution:

- Accept exactly one read-only `SELECT` statement.
- Allow only approved views and approved output columns.
- Reject projection wildcards: `SELECT *` and `SELECT alias.*`.
- Permit `COUNT(*)`; it is a single aggregate value, not a projection wildcard.
- Require bounded time/scope filters for detail queries.
- Require a server-enforced detail-row limit no greater than the MCP response
  budget; do not trust a model-supplied `LIMIT` alone.
- Reject writes, DDL, multiple statements, unapproved joins, system catalogues,
  data-changing CTEs, locking clauses, and expensive functions.
- Execute under a read-only database role, read-only transaction, statement
  timeout, and MCP response-byte limit.

Run `sql-policy-cases.json` in this references directory against the workplace validator.
If the validator cannot pass them, remove the SQL-text tool from the Agent and
Gateway allowlists rather than relying on this skill.
