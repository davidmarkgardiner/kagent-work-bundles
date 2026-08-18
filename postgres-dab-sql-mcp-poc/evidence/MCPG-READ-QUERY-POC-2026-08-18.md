# MCPg read-only query POC — live evidence

Date: 2026-08-18
Environment: HomeLab Kubernetes context `red`, synthetic PostgreSQL fixture
Scope: one bounded namespace-count query through kagent and MCPg

## Verdict

**PASS.** MCPg read-only mode answered a namespace-count question through its
native `run_select` tool. The proof did not require database write access,
MCPg `restricted` mode, or an `execute_sql` tool.

## Live result

The disposable kagent Agent mounted only `list_tables`, `describe_table`, and
`run_select` from the existing read-only `RemoteMCPServer/mcpg-readonly-spike`.
It called `run_select` with:

```sql
SELECT count(DISTINCT namespace_name) AS distinct_namespaces
FROM public.v_namespace_image_summary;
```

The MCP response had `row_count: 1`, `truncated: false`, and returned
`distinct_namespaces: 3`. The final Agent response included both
`MCPG_READ_QUERY_REPLY_OK` and the same count.

The machine-readable A2A receipt is
[MCPG-READ-QUERY-A2A-RECEIPT-2026-08-18.json](MCPG-READ-QUERY-A2A-RECEIPT-2026-08-18.json).
It contains synthetic data only.

## Work configuration implication

The optional
[read-query profile](../work-lift-and-shift/mcpg-read-query-profile/) keeps
`MCPG_ACCESS_MODE=read-only` and adds only MCPg `run_select` to both the Agent
Gateway policy and the dedicated query Agent. The work database principal must
remain SELECT-only against owner-approved views.

`execute_sql` is not MCPg v0.7.1's normal read-query tool. It was associated
with the legacy CrystalDBA spike, which is not part of the current work bundle.
MCPg `restricted` enables write tools and is deliberately outside this POC.

## Not proven

- connectivity, TLS, database grants, schemas, views, and results in work;
- Agent Gateway CRD compatibility in work; or
- any write, DDL, export, unrestricted query, or production-data access.

Those remain explicit outside-in validation gates before a work deployment.
