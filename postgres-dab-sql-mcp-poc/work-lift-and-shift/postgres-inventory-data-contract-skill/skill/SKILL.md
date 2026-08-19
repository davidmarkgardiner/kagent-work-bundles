---
name: postgres-inventory-data-contract
description: Answer approved AKS estate, application-directory, and namespace-inventory questions through the mounted read-only MCPg tools. Use for PostgreSQL inventory questions that need the approved view catalogue, safe query procedure, definitions, and response format.
---

# PostgreSQL inventory data contract

Use this skill only with the approved PostgreSQL inventory views and the
mounted MCPg read-only tools. Treat the database role, MCPg mode, and Agent
Gateway allowlist as enforcement boundaries; this skill is not permission to
access additional data.

## Workflow

1. Identify the requested data product: AKS estate, application directory, or
   namespace inventory.
2. Use the approved-view catalogue in
   `references/approved-views.md`. If the requested metric is not listed,
   say that it needs data-owner approval; do not guess table or column names.
3. If the catalogue version is stale or insufficient, use `list_tables` or
   `describe_table` only to verify the approved view's live shape.
4. Use `run_select` for one read-only `SELECT` against an approved view. Use
   aggregates, explicit columns, filters, and a small `LIMIT` where a list is
   required. Never use `SELECT *`.
5. Return the result, source view, filters, grouping, and a short caveat about
   missing or null data. State when the question cannot be answered from the
   approved views.

## Guardrails

- Never write, change schema, run DDL, or make multiple statements.
- Never query base tables, system catalogues, or an unapproved view.
- Never return credentials, tokens, raw owner contact details, or sensitive
  tags. Prefer counts and grouped summaries.
- Do not invent a join, identifier mapping, ownership definition, or data
  freshness date. Escalate the gap to the data owner.
- Do not expose raw SQL unless the requester is an approved operator and the
  query has already passed the approved-view boundary.

## Standard response

Use this structure:

```text
Result: <concise answer>
Source: <approved view>
Method: <aggregate/filter/grouping, not raw SQL>
Caveat: <freshness, null, or scope limitation>
```

## References

- Read `references/approved-views.md` before selecting a data source.
- Read `references/query-catalogue.md` when the request resembles a supported
  question. Treat all names there as placeholders until the data owner has
  approved the work catalogue.
