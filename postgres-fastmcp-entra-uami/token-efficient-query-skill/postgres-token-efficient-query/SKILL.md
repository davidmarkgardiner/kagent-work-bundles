---
name: postgres-token-efficient-query
description: Answer PostgreSQL questions through bounded MCP tools without loading bulk result sets into model context. Use for counts, summaries, trends, filtered detail, truncation handling, and approved export decisions.
---

# Token-efficient PostgreSQL queries

Use the narrowest approved MCP operation that answers the question. Prefer
database-side counts, grouping, trends, and explicit filters over detail rows.
The database may process a large data set; the model should receive only the
small answer needed for reasoning.

## Query procedure

1. Confirm the requested scope, measure, grouping, and time range. Ask for one
   missing filter when its absence would produce a broad detail result.
2. Prefer a typed aggregate or summary tool. Use a detail tool only when the
   user needs named records and select only necessary fields.
3. Treat `truncated: true` as a stopping condition. Report the truncation and
   request a narrower filter; do not retry, page repeatedly, or reconstruct an
   export in chat.
4. For a complete data set, use the separately approved export workflow and
   return only its reference and metadata. Never place the export contents in
   the conversation.

## Boundaries

- The MCP service, Gateway allowlist, approved views, and database grants are
  the enforcement layers. This skill grants no access.
- Never request arbitrary SQL when typed tools can answer the question.
- If a legacy tool accepts SQL, read
  [`references/legacy-sql-policy.md`](references/legacy-sql-policy.md) before
  using it, then run its linked policy cases. The server must enforce that
  policy; these instructions do not.
- Never expose credentials, tokens, personal contact data, or unapproved
  columns in an answer or evidence receipt.

## Response shape

State the concise result, approved source/view, filters or grouping, freshness,
and whether it was truncated. Do not reproduce query text unless an approved
operator explicitly needs it for review.
