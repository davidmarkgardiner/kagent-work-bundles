# Typed-tool routing template

Replace this table with the exact tools already exposed at work or with a
separately reviewed typed-tool iteration. Descriptions should make tool choice
obvious without loading database schema into every prompt.

| User intent | Preferred tool | Required inputs | Database-side work | Maximum chat result | Do not use when |
|---|---|---|---|---|---|
| One KPI | `{{GET_METRIC_TOOL}}` | metric, time range, bounded filters | Aggregate | One row | User needs a trend or breakdown |
| Breakdown/top values | `{{GET_BREAKDOWN_TOOL}}` | metric, dimension, time range, `top_n <= {{MAX_TOP_N}}` | Filter, group, sort, limit | `{{MAX_GROUP_ROWS}}` rows | Dimension is not approved for metric |
| Time trend | `{{GET_TREND_TOOL}}` | metric, date range, approved interval | Aggregate into time buckets | `{{MAX_BUCKETS}}` rows | Requested range cannot fit bounded buckets |
| Exact record | `{{GET_RECORD_TOOL}}` | stable identifier, field set | Exact indexed lookup | One row | Identifier is missing or request is bulk |
| Find a dimension value | `{{SEARCH_DIMENSION_TOOL}}` | term, `limit <= {{MAX_LOOKUP_ROWS}}` | Bounded indexed/search lookup | `{{MAX_LOOKUP_ROWS}}` identifiers/labels | Caller requests all distinct values |
| Full dataset | `{{CREATE_ANALYSIS_JOB_OR_EXPORT_TOOL}}` | approved scope and destination policy | Asynchronous job outside chat | Metadata/resource link only | User only needs a summary |

## Selection rules

- Prefer an existing verified aggregate tool over generating SQL.
- Apply owner-approved default filters before execution and state them in the
  answer.
- If a breakdown would exceed the row budget, require `top_n`, combine a safe
  remainder as `other`, or ask for a narrower filter.
- Never satisfy an export by looping a detail tool.
- Never call a schema-listing tool as routine preamble. If semantic routing
  fails, retrieve only the relevant domain/table/column metadata and stop after
  the configured discovery budget.
