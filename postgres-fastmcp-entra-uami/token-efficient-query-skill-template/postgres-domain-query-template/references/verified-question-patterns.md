# Verified question-pattern template

Maintain a small set of common, data-owner-reviewed patterns. These are routing
examples for typed tools, not permission to expose SQL or bypass server checks.

## Pattern: scalar metric

- User phrasing: `What was {{METRIC}} for {{TIME_RANGE}}?`
- Tool: `{{GET_METRIC_TOOL}}`
- Parameters: `metric={{METRIC_ID}}`, `time_range={{NORMALIZED_RANGE}}`
- Expected shape: one value, unit, as-of time, applied filters
- Clarify when: `{{AMBIGUITY_RULE}}`

## Pattern: bounded breakdown

- User phrasing: `Show the top {{N}} {{DIMENSION}} by {{METRIC}}.`
- Tool: `{{GET_BREAKDOWN_TOOL}}`
- Parameters: metric, dimension, time range, `top_n=min(N, {{MAX_TOP_N}})`
- Expected shape: no more than `{{MAX_TOP_N}}` grouped rows
- Clarify when: dimension is incompatible with the metric or no time range has
  an approved default

## Pattern: trend

- User phrasing: `How has {{METRIC}} changed over {{TIME_RANGE}}?`
- Tool: `{{GET_TREND_TOOL}}`
- Parameters: metric, range, interval selected to remain within
  `{{MAX_BUCKETS}}` buckets
- Expected shape: bounded time buckets plus concise direction/variance summary
- Clarify when: the requested resolution would exceed the bucket budget

## Pattern: bulk request

- User phrasing: `Give me all {{RECORDS}}.`
- Tool: none in chat; offer `{{CREATE_ANALYSIS_JOB_OR_EXPORT_TOOL}}` if approved
- Expected shape: job/resource metadata only
- Never: page through detail results or paste an export into the conversation
