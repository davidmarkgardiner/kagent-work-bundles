# Starburst/Trino data-mesh MCP HomeLab POC

Status: **live fallback proof PASS — option C.** This is not a Starburst Enterprise
proof. The 2026-08-12 `red` HomeLab run passed the Trino synthetic-query,
RemoteMCPServer discovery, kagent Agent readiness, **and one completed
conversational A2A request that used the constrained MCP tool and returned the
expected aggregate**. See [evidence/POC-RUN-2026-08-12.md](evidence/POC-RUN-2026-08-12.md)
and its [redacted A2A receipt](evidence/A2A-CONVERSATIONAL-RECEIPT-2026-08-12.json).
Starburst Enterprise has a native MCP endpoint, but its supported
Kubernetes deployment requires a Starburst Harbor account, SEP licence, and a
valid MCP-server licence. None is present in this public repository or HomeLab
preflight.

This disposable POC proves a narrower fact:

    kagent -> RemoteMCPServer -> constrained MCP adapter -> Trino -> synthetic data

It does **not** prove Starburst Enterprise licensing, data-product feature,
native MCP endpoint, production authentication, governance, audit/query IDs,
or performance. It also does not prove Microsoft Data API Builder (DAB) SQL
MCP: DAB is a viable official direct-SQL pattern, but it is not the closest
match for a Starburst data-mesh endpoint.

## Why the fallback is safe

- The Trino memory catalog contains only the seed Job's three synthetic rows.
- The adapter does not expose arbitrary SQL, DDL, DML, credentials, or write
  tools.
- It exposes only discovery, fixed metadata, and a fixed aggregate.
- The adapter has no Kubernetes service-account token.
- The kagent Agent mounts exactly three discovered tool names.
- The resources are disposable and stay on the \`red\` HomeLab context.

## Run and verify

    sh work-agent-bundles/starburst-trino-data-mcp-poc/scripts/deploy.sh red
    sh work-agent-bundles/starburst-trino-data-mcp-poc/scripts/verify.sh red

Expected verifier markers:

    TRINO_SYNTHETIC_QUERY_OK
    TRINO_SEED_JOB_COMPLETED_OK
    REMOTE_MCP_DISCOVERY_OK
    KAGENT_AGENT_READY_OK
    A2A_TOOL_CALL_OK
    A2A_CONVERSATIONAL_RESPONSE_OK
    VERIFY_PASS

The deploy script deliberately recreates the disposable seed Job and seeds the
same three rows with `DROP TABLE IF EXISTS` followed by `CREATE TABLE`; this
makes a redeploy deterministic after a Trino restart. A verifier run after the retained Job
receipt has expired reports `TRINO_SEED_JOB_RECEIPT_EXPIRED` but still requires
the direct live query to pass.

## Conversational acceptance proof

The normal verifier now includes the A2A acceptance gate. It makes a fresh
live call; it requires a terminal `completed` task, `isError:false` from
`get_overdue_risk_summary`, the `DATA_MCP_REPLY_OK` marker, and the synthetic
high/medium/low counts `3`, `7`, and `12`. The equivalent direct command is:

    scripts/kagent-a2a-invoke.sh \
      --agent trino-data-product-lab-agent --ns kagent --context red --timeout 180 \
      --receipt-file /tmp/trino-a2a-receipt.json \
      --text 'Use get_overdue_risk_summary. Reply with exactly: DATA_MCP_REPLY_OK, followed by the risk bands and account counts.'

The first captured acceptance run produced a terminal `completed` task, an
`isError:false` response from `get_overdue_risk_summary`, and final agent text:

    DATA_MCP_REPLY_OK, high: 3, low: 12, medium: 7

The shared caller now captures its raw task receipt on request and falls back
to the final text-bearing agent-history message when a completed response has
no `result.artifacts` projection. It also removes `<think>...</think>` blocks
from normal user-facing output; the optional raw receipt is owner-only and is
for diagnostics, not publication. This fixes the **evidence-capture** failure;
it is not a claim that every kagent runtime/version has perfect non-streaming
A2A behaviour. Treat absent terminal text, a non-completed task, an MCP
`isError:true` result, missing marker, or incorrect synthetic counts as a
failed acceptance run.

## Starburst handoff

To replace this fallback with the production-equivalent path, Starburst must
supply a sanctioned non-production SEP environment or evaluation package,
Harbor/chart access, SEP and MCP licences, an approved identity/auth method,
and one synthetic or masked data product. Then replace the adapter endpoint
with SEP's authenticated \`https://{{STARBRUST_COORDINATOR}}/mcp\` endpoint,
inspect discovered tools, and mount only the agreed discovery and
parameterised-query tools.

See the [data MCP plan](../../platform/data-mcp/README.md#starburst-data-mesh-poc-decision-and-handoff-plan)
for the decision gates and evidence contract.

For the honest production-fit comparison, exact tested images, air-gapped
registry preparation, and office native-Starburst runbook, see
[OFFICE-REPLICATION.md](OFFICE-REPLICATION.md).

## Cleanup

    sh work-agent-bundles/starburst-trino-data-mcp-poc/scripts/teardown.sh red
