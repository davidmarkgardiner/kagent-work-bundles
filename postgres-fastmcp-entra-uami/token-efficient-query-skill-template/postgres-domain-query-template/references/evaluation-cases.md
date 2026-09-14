# Evaluation-case template

Populate at least ten representative questions from sanitized usage. Store no
workplace rows or identifiers. For each case record:

| Field | Required value |
|---|---|
| Question | Sanitized user phrasing |
| Classification | scalar, breakdown, trend, record, search, comparison, export, or unsupported |
| Expected tool | Exact typed tool or no tool |
| Expected parameters | Required filters, grouping, time range, fields, and limit |
| Forbidden calls | Broad/detail/schema/paging calls that must not occur |
| Maximum calls | Normally one; justify any higher value |
| Maximum MCP transport bytes | `{{PER_CASE_TRANSPORT_BYTE_CAP}}` |
| Expected result shape | Scalar or bounded rows; never real values in Git |
| Truncation behaviour | Stop and narrow, or route to an approved job/export |

Include cases for:

1. a common scalar metric;
2. a bounded top-N breakdown;
3. a trend whose interval must be coarsened;
4. an ambiguous business term that requires clarification;
5. an exact identifier lookup;
6. a high-cardinality name lookup;
7. a request for all rows;
8. a request for an unapproved field;
9. a truncated result that must not trigger paging; and
10. a second user turn proving old row payloads are not carried unnecessarily.

Measure response bytes, transport-envelope bytes, input tokens per model call,
and cumulative session tokens. Accuracy, authorization, and token-budget checks
must all pass; a smaller but wrong answer is not success.
