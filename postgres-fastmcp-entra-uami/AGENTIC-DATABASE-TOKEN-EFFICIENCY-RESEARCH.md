# Agentic database interrogation and token efficiency

Research checked: 2026-09-08. This note summarizes external primary sources and
relates them to the PostgreSQL MCP upgrade; it does not endorse a vendor.

## Verdict

The current direction is sound for operational questions: typed aggregate
tools, approved semantic views, server-side result budgets, explicit
truncation, and a domain skill are consistent with established approaches.

MCP is not inherently the wrong transport. An MCP tool that returns thousands
of rows into every model turn is the wrong interface. If the main requirement
is unconstrained exploration or analysis of full datasets, use a governed
analytical worker/notebook/query service that keeps data outside the chat
context and returns a concise result plus an intentionally fetched artifact.

## What other systems do

### Curate semantics instead of exposing the whole schema

Snowflake recommends semantic views with explicit relationships, metrics,
filters, business descriptions, verified queries, and an evaluation loop. It
also recommends starting with 5–10 tables and one domain rather than modeling
an entire warehouse. Databricks Genie similarly uses focused data sources,
business instructions, example questions/queries, parameterized trusted assets,
functions, join specifications, and benchmarks.

This supports one small domain skill per data product. The skill should contain
logical grain, metrics, dimensions, synonyms, valid relationships, common
question patterns, and tool routing—not exhaustive DDL or sample data.

Sources:

- Snowflake semantic-view practices: https://docs.snowflake.com/en/user-guide/views-semantic/best-practices-modeling
- Snowflake verified query repository: https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository
- Databricks Genie quality guidance: https://docs.databricks.com/aws/en/genie-agents/tune-quality

### Retrieve only relevant schema when generation is unavoidable

Text-to-SQL research continues to treat schema selection/linking as a distinct
stage. A 2025 context-aware bidirectional retrieval paper reports that selecting
question-relevant schema outperformed full-schema baselines on its evaluated
benchmarks. That does not prove the same gain for this workplace, but it argues
against inserting the full enterprise schema into every prompt.

Source: https://arxiv.org/abs/2510%2E14296

### Keep bulk data out of the tool result

The MCP specification allows a tool to return a resource link that a client can
fetch deliberately. It also notes that structured content is commonly mirrored
as serialized text for backwards compatibility. Our GEEKOM receipt observed
that effect: 12,440 bytes of adapter data became a 24,963-byte transport
envelope. Therefore the budget must cover the complete client-visible MCP
envelope, not only the Python object before serialization.

For large output, return a small status/summary object and a governed,
short-lived resource reference. Do not embed the resource or automatically read
it back into the same model context. Verify client support and authorization
before adopting this pattern.

Source: https://modelcontextprotocol.io/specification/draft/server/tools

### Compact conversation state, but only as a second line of defence

kagent supports invocation- and token-triggered event compaction, overlap,
retention, and optional summarization. Its documentation specifically recommends
compaction for long conversations and agents with large tool outputs. Enable
and test this below the model's hard context limit, but do not use compaction to
justify oversized database responses: the first large result has already
consumed input tokens and may have displaced useful context.

Source: https://kagent.dev/docs/kagent/concepts/agents/

## Recommended architecture

```text
user question
  -> small domain router/skill
     -> verified typed metric, trend, breakdown, or lookup tool
        -> database performs filter/aggregate
        -> small bounded MCP envelope
     -> or governed asynchronous analysis/export job
        -> data stays outside chat
        -> summary + metadata + deliberate resource link
  -> session token telemetry and kagent compaction
```

Use four lanes:

1. **Known operational questions:** typed parameterized tools returning scalars
   or a small number of groups.
2. **Semantic discovery:** retrieve only the relevant domain, metrics,
   dimensions, and tool descriptions; never the entire schema or distinct-value
   population.
3. **Open-ended analysis:** execute in a controlled analysis worker with its own
   bounded context and artifact store, then return a concise synthesis.
4. **Exports:** an explicitly approved out-of-band workflow, never repeated MCP
   pagination in the chat session.

## What to measure at work

Before choosing limits or deciding the tool is unsuitable, capture for a small
sanitized evaluation set:

- MCP calls and retries per question;
- adapter payload and complete transport-envelope bytes;
- model input/output tokens per call and cumulative tokens per session;
- rows scanned by PostgreSQL versus rows returned to the model;
- whether structured content is duplicated into text by the installed client;
- compaction trigger, retained events, summary size, and answer continuity;
- correctness against owner-approved expected tool/parameters/result shape; and
- p50/p95 latency and failure rate.

The immediate success criterion is not merely “under 250,000 tokens.” A common
question should normally take one bounded tool call, remain far below the
configured per-call context budget, and avoid carrying raw rows into later
turns. Set the actual byte, row, call, and compaction thresholds from the
baseline rather than guessing them in this public bundle.

## Decision point

Keep the MCP approach if typed questions are accurate, bounded, observable, and
materially cheaper after the canary. Introduce a dedicated semantic-query layer
if users need broader natural-language coverage than maintained tools provide.
Use a separate analytical job/notebook path if users genuinely need iterative
work over large result sets. Retire or sharply restrict any generic SQL MCP that
cannot prevent bulk results, repeated paging, and schema/context flooding.
