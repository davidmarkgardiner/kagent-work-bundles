# Starburst/Trino data-mesh MCP HomeLab POC

Status: **live fallback proof PASS — option C.** This is not a Starburst Enterprise
proof. The 2026-08-12 `red` HomeLab run passed the Trino synthetic-query,
RemoteMCPServer discovery, and kagent Agent readiness verifier. See
[evidence/POC-RUN-2026-08-12.md](evidence/POC-RUN-2026-08-12.md). Starburst Enterprise has a native MCP endpoint, but its supported
Kubernetes deployment requires a Starburst Harbor account, SEP licence, and a
valid MCP-server licence. None is present in this public repository or HomeLab
preflight.

This disposable POC proves a narrower fact:

    kagent -> RemoteMCPServer -> constrained MCP adapter -> Trino -> synthetic data

It does **not** prove Starburst Enterprise licensing, data-product feature,
native MCP endpoint, production authentication, governance, or performance.

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
    REMOTE_MCP_DISCOVERY_OK
    KAGENT_AGENT_READY_OK
    VERIFY_PASS

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

## Cleanup

    sh work-agent-bundles/starburst-trino-data-mcp-poc/scripts/teardown.sh red
