# MCPg password-bundle query catalogue template

Status: **illustrative.** Approve and replace the view/column names before
using these patterns in work.

| User question | Approved pattern | Required response caveat |
|---|---|---|
| How many namespaces are there? | Count distinct approved namespace values in `approved_namespace_inventory`. | State the view and whether null namespace values were excluded. |
| Which LOBs own the most namespaces? | Group the namespace view by LOB and count distinct namespaces. | State the reporting-date or freshness field. |
| Which clusters are in a region? | Filter the estate view by a supplied region and return a bounded list of cluster names and types. | State that only approved inventory coverage is represented. |
| Who owns a namespace? | Filter namespace inventory by exact namespace and return the approved ownership summary. | Do not return personal contact information. |
| What stream owns an application? | Filter application directory by its approved stable application key. | State if the directory record is absent or ambiguous. |

## Query rules

- Prefer `count`, `count(distinct ...)`, `group by`, and filtered summaries.
- Require an exact namespace, application key, region, or other approved
  predicate for detailed listings.
- Use an explicit low row limit for lists. A request for a full export is out
  of scope.
- If a question needs a cross-product join, use it only after the data owner
  adds that join and its stable key to `approved-views.md`.
