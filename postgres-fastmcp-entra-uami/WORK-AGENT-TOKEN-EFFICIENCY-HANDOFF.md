# Work-agent handoff: PostgreSQL MCP token-efficiency upgrade

## Objective

Upgrade the existing workplace PostgreSQL MCP so large database operations do
not place bulk rows into model context. Preserve the current authentication
mode, approved views, caller controls, and database grants.

## Workplace starting point and non-goals

The workplace PostgreSQL MCP is already deployed. Treat this repository as a
sanitized reference implementation and test package, not as a manifest set to
apply wholesale.

Do not recreate, replace, or migrate the existing MCP, namespace, Secret,
ServiceAccount, Gateway, RemoteMCPServer, Agent, authentication mode, database
principal, approved views, or grants as part of this change. Do not run the
README's password-first or UAMI deployment walkthrough. Those instructions
document how the original bundle is assembled and are reference-only for this
upgrade.

Start from the deployed workplace source and manifests. Produce a reviewed diff
that ports only the applicable changes below while retaining workplace object
names, identity wiring, policies, tool contracts, registry, and delivery flow.

## Delta change map

Port these changes onto the currently deployed implementation rather than
replacing it with this bundle:

| Reference | Delta to port |
|---|---|
| `adapter/result_budget.py` | Add the fail-closed row, response-byte, and per-cell result envelope with compiled ceilings. |
| `adapter/server.py` | Use `fetchmany(max_rows + 1)`, a read-only transaction, bounded statement timeout, and the result envelope. Adapt this to the workplace tool functions; do not replace unrelated tools or SQL. |
| `adapter/Dockerfile` | Include the new budget module and only the verifiers required by the workplace image/test flow. |
| `adapter/test_result_budget.py` and `adapter/test_server.py` | Port the budget and tool-contract tests into the workplace test layout. |
| `adapter/verify_budget_live.py` and `adapter/verify_mcp_transport.py` | Reuse or adapt the marker-only direct and Streamable HTTP checks without recording workplace rows. |
| Agent system instruction in both reference manifests | Add the truncation stopping rule to the existing Agent; do not replace the Agent manifest. |
| `token-efficient-query-skill/` | Use the generic POC skill only as behavioural reference and regression evidence. Do not install it unchanged at work. |
| `token-efficient-query-skill-template/postgres-domain-query-template/` | Copy, rename, and populate the template with the approved workplace semantics, typed-tool routing, and sanitized evaluations. |
| `token-efficient-query-skill/postgres-token-efficient-query/references/sql-policy-cases.json` | Use only if the deployed MCP already exposes SQL text. Do not add such a tool. |

Do not assume filenames or framework structure match at work. The required
outcome is the same server-side behaviour and test evidence, expressed as the
smallest reviewable patch against the deployed version.

## Source package

Use this directory as the source of truth. The implementation is in `adapter/`,
the behavioural skill is in `token-efficient-query-skill/`, and repeatable
acceptance tests are in `tests/local-k8s/`.

The sanitized GEEKOM test receipt is
`evidence/TOKEN-EFFICIENCY-GEEKOM-POC-2026-09-08.md`.
The external design review and decision criteria are in
`AGENTIC-DATABASE-TOKEN-EFFICIENCY-RESEARCH.md`.

Do not copy credentials, endpoints, identity IDs, database coordinates, query
results, or workplace SQL into this public repository or handoff evidence.

## Required discovery before changing work

1. Identify the deployed image digest, MCP implementation/version, Kubernetes
   objects, Gateway policy, Agent tool allowlist, authentication mode, and
   rollback digest.
2. Determine whether the Agent has only typed tools or also has an SQL-text tool
   such as `run_select`. Do not infer this from public manifests.
3. Record current MCP response bytes and model input tokens for sanitized,
   representative aggregate and broad-result questions. Inspect the installed
   Agent Gateway metrics rather than assuming metric names are unchanged.

## Iterative upgrade sequence

1. **Baseline:** inventory the deployed objects and digests, capture the current
   bounded test questions, response bytes, and model input tokens, and save the
   current image and Agent manifest as rollback inputs.
2. **Adapter patch:** port only the server-side budget and its tests into the
   workplace source. Review the diff against the deployed version.
3. **Image:** build in approved CI, run tests, scan, sign, publish, and record an
   immutable internal image digest. Do not change authentication or grants.
4. **Adapter canary:** update only the image/configuration needed for one
   reversible lower-environment or canary instance. Prove direct MCP and
   Streamable HTTP bounds before changing Agent behaviour.
5. **Agent instruction and skill canary:** add the truncation stopping rule and,
   if compatible, attach the immutable populated workplace skill image to the
   existing Agent. Do not install the generic or unfilled template and do not
   replace its other instructions, tools, identity, or Gateway wiring.
6. **End-to-end comparison:** prove discovery, readiness, a sanitized A2A
   question, and no automatic paging. Inspect text/structured-content
   duplication, compare response bytes and per-call/cumulative input tokens with
   the baseline, and test kagent compaction below the model's hard limit.
7. **Decision gate:** report the exact workplace diff, digests, evidence,
   measured change, and rollback. Stop before wider or production promotion.

Retain only counts, limits, timings, hashes, and correlation IDs in evidence—not
database rows.

## Primary lane: typed FastMCP

The typed-tool lane is the default. Preserve every existing tool name,
parameter, approved query, and allowlist unless a separately reviewed workplace
change requires otherwise. Add the result budget around their returned rows;
do not import the public POC's three example tools merely because they exist in
this directory.

Default limits are 50 rows, 32 KiB of adapter data, 512 characters per cell,
and a five-second statement timeout. Configuration may lower them but cannot
raise the compiled ceilings.

## Optional legacy lane: SQL-text tool

Do not add an SQL-text tool to typed FastMCP. If the workplace deployment
already exposes one, the skill is not sufficient enforcement. Put an
AST-parsing validator in the server path and run every case in
`token-efficient-query-skill/postgres-token-efficient-query/references/sql-policy-cases.json`.

Projection wildcards must fail while `COUNT(*)` remains allowed. Enforce views,
columns, filters, row limits, read-only transactions, timeouts, and output
budgets outside the model. If this cannot be proven, remove the SQL-text tool
from both the Agent and Gateway allowlists.

## Skill deployment

The packaged `postgres-token-efficient-query` skill proves the generic behaviour
in the public POC; it does not know the workplace data contract and must not be
installed unchanged.

Copy `token-efficient-query-skill-template/postgres-domain-query-template/` to a
new, appropriately named workplace skill. Replace every placeholder with
data-owner-approved information, keeping the entrypoint short and placing
conditional domain detail in its references. Populate:

- logical source, grain, freshness, and scope;
- approved metrics, dimensions, filters, relationships, business terms, and
  sensitive/large-field exclusions;
- exact typed-tool routing, required parameters, top-N/bucket/lookup limits, and
  the separate export or analysis-job route;
- a small set of common verified question patterns; and
- at least ten sanitized evaluations covering ambiguity, high cardinality,
  truncation, forbidden fields, exports, and a follow-up turn.

Rename both paths in `token-efficient-query-skill-template/Dockerfile.template`
to match the copied skill. Validate the populated skill and installed kagent
CRD schema, then build, publish, and attach the workplace skill by immutable
internal digest under the existing Agent's `spec.skills.refs`. The skill
improves tool selection and truncation handling; it is not a permission
boundary.

## Session-context backstop

Inspect the installed kagent version and configure its supported context
compaction fields using a threshold safely below the active model's hard context
window. Measure when compaction occurs, what events remain, summary size, and
answer continuity. Do not copy values from this public bundle without a
workplace baseline. Server-side result limits remain the primary control because
compaction occurs after tool data has already entered at least one model call.

## Acceptance gates

- Bundle verifier, contract tests, public-safety scan, image scan/signature, and
  server-side Kubernetes dry-run pass.
- A source query matching thousands of rows returns no more than the configured
  row and byte budgets with `truncated: true`.
- The Streamable HTTP MCP response retains the bounded result and truncation
  metadata.
- The complete client-visible transport envelope is measured, including any
  structured-content copy serialized into text.
- The Agent reports truncation and does not auto-page.
- Projection `SELECT *` and `alias.*` fail if an SQL-text lane exists;
  `COUNT(*)` against an approved view passes.
- Database base-table access and all writes remain denied.
- Before/after response bytes and model input-token measurements demonstrate
  the reduction using sanitized evidence.
- Per-call and cumulative session-token telemetry show that representative
  follow-up conversations remain within the approved operating budget, and
  compaction triggers before the model's hard context limit without preserving
  old raw row payloads.

## Rollback

Restore the recorded previous adapter and skill image digests and the previous
Agent manifest. Do not change database grants during application rollback.
Confirm readiness and one bounded read after rollback.
