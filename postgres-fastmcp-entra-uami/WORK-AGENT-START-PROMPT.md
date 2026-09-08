# Work-agent start prompt

Upgrade the installed workplace PostgreSQL MCP using
`WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md` and this bundle as the sanitized source
package.

The workplace MCP is already deployed. This is an incremental upgrade, not a
greenfield installation: do not apply either Kustomize tree wholesale and do
not recreate or migrate the MCP, Secret, ServiceAccount, Gateway, Agent,
authentication, approved views, or database grants. Diff the deployed workplace
source and manifests against the change map in the handoff, then port only the
applicable token-efficiency deltas.

First inspect the actual deployed MCP, Agent, Agent Gateway policy, kagent CRD,
authentication mode, approved-view boundary, image digest, and rollback digest.
Do not assume the public POC matches work. Preserve authentication and database
grants during this change.

Implement and prove the fail-closed row, byte, cell, and statement-time budgets.
Build and attach the token-efficient query skill by immutable internal digest.
If an SQL-text tool exists, use an AST validator and pass every supplied policy
case; do not rely on prompts or regex, and do not add SQL-text capability where
it does not already exist.

Use a lower environment or reversible canary first. Capture sanitized before
and after MCP response bytes and model input-token counts, plus readiness,
discovery, truncation, no-auto-pagination, database-denial, and rollback
evidence. Never record rows, queries containing workplace identifiers,
credentials, endpoints, tokens, database coordinates, or private identity IDs.

Stop before production promotion. Return the exact changed paths, image and
skill digests, tests, evidence locations, remaining gates, rollback digest, and
the explicit approval needed for wider rollout.
