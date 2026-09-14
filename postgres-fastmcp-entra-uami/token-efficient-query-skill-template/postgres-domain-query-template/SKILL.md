---
name: postgres-domain-query-template
description: Template for creating a domain-specific PostgreSQL query skill that routes business questions to bounded typed MCP tools using curated data semantics, verified question patterns, and strict context budgets.
---

# PostgreSQL domain query template

Copy and rename this skill before use. Replace every `{{PLACEHOLDER}}`, remove
irrelevant examples, and have the data owner approve the populated references.
Do not install this unfilled template on an Agent.

## Query routing

1. Classify the request as a scalar metric, grouped summary, trend, record
   lookup, bounded search, comparison, or full-data export.
2. Read [`references/tool-routing.md`](references/tool-routing.md) and choose the
   narrowest typed tool whose stated purpose matches the request.
3. Read [`references/data-contract.md`](references/data-contract.md) only when
   metric, dimension, grain, freshness, or business-term semantics are needed.
4. Read
   [`references/verified-question-patterns.md`](references/verified-question-patterns.md)
   when the question resembles a maintained high-frequency pattern.
5. Ask for one missing filter when it materially changes scope. Prefer a
   sensible approved default only when the data contract defines one.
6. Treat `truncated: true` as a stopping condition. Never page repeatedly,
   split a broad request into many calls, or reconstruct an export in chat.

## Context discipline

- Prefer one scalar or grouped response over detail rows.
- Request only the fields needed for the answer and use a small `top_n`.
- Do not fetch schema, distinct values, or sample rows unless the selected tool
  requires that discovery. Use bounded lookup tools for high-cardinality names.
- Return the answer, filters, time range, freshness, source data product, and
  truncation state. Do not echo tool JSON, schema definitions, or SQL.
- A full data set belongs in the approved asynchronous export or analysis-job
  path. Return only status, row count, expiry, checksum, and a resource
  reference that the client can fetch deliberately.

## Enforcement boundary

The skill improves routing; it is not a security or size boundary. The MCP
server must enforce approved views, columns, parameters, row and byte budgets,
read-only execution, statement timeout, and caller authorization. Do not add an
arbitrary SQL tool. If one already exists, retain it only behind a reviewed AST
policy and separate acceptance tests.

Run the populated cases in
[`references/evaluation-cases.md`](references/evaluation-cases.md) before
deployment and after any data-contract or tool change.
