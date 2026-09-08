# Work-agent handoff: PostgreSQL MCP token-efficiency upgrade

## Objective

Upgrade the existing workplace PostgreSQL MCP so large database operations do
not place bulk rows into model context. Preserve the current authentication
mode, approved views, caller controls, and database grants.

## Source package

Use this directory as the source of truth. The implementation is in `adapter/`,
the behavioural skill is in `token-efficient-query-skill/`, and repeatable
acceptance tests are in `tests/local-k8s/`.

The sanitized GEEKOM test receipt is
`evidence/TOKEN-EFFICIENCY-GEEKOM-POC-2026-09-08.md`.

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

## Primary lane: typed FastMCP

1. Apply the adapter changes from this package. Preserve password versus UAMI
   wiring; do not change authentication while making this upgrade.
2. Run `scripts/verify-bundle.sh` and the adapter tests.
3. Build in approved CI, scan, sign, publish, and record an immutable internal
   image digest.
4. Deploy one reversible lower-environment/canary instance with the existing
   approved database view and identity.
5. Prove the MCP response envelope, Gateway discovery, Agent readiness, and a
   sanitized A2A question. A truncated response must not cause automatic paging.
6. Compare response bytes and model input tokens with the baseline before wider
   rollout. Retain only counts, limits, timings, hashes, and correlation IDs in
   evidence—not database rows.

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

Build `token-efficient-query-skill/Dockerfile`, publish it to the approved
internal registry by immutable digest, and add that digest under the kagent
Agent's `spec.skills.refs`. Validate the exact skill schema against the
installed kagent CRD. The skill improves tool selection and truncation handling;
it is not a permission boundary.

## Acceptance gates

- Bundle verifier, contract tests, public-safety scan, image scan/signature, and
  server-side Kubernetes dry-run pass.
- A source query matching thousands of rows returns no more than the configured
  row and byte budgets with `truncated: true`.
- The Streamable HTTP MCP response retains the bounded result and truncation
  metadata.
- The Agent reports truncation and does not auto-page.
- Projection `SELECT *` and `alias.*` fail if an SQL-text lane exists;
  `COUNT(*)` against an approved view passes.
- Database base-table access and all writes remain denied.
- Before/after response bytes and model input-token measurements demonstrate
  the reduction using sanitized evidence.

## Rollback

Restore the recorded previous adapter and skill image digests and the previous
Agent manifest. Do not change database grants during application rollback.
Confirm readiness and one bounded read after rollback.
