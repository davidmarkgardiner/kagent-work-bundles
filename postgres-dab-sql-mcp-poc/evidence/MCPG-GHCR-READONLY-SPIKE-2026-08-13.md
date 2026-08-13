# MCPg GHCR read-only spike — 2026-08-13

## Verdict

**PASS — bounded HomeLab proof only.** The pre-built MCPg GHCR image ran as a
read-only Streamable HTTP PostgreSQL MCP server, kagent discovered its tools,
and a constrained agent answered a schema question using only its permitted
tools.

## Live facts

| Check | Result |
| --- | --- |
| Cluster | `red` HomeLab; synthetic PostgreSQL only |
| Image pulled | `ghcr.io/devopam/mcpg@sha256:f16f97f667832b79ca496f9cbae8a0485ab1fb59beb32a158db4af3da4ada1d9` |
| Runtime mode | `MCPG_ACCESS_MODE=read-only`, Streamable HTTP `/mcp` on port 8000 |
| Database principal | Existing synthetic `postgres-dab-poc-reader` secret; no credential value was read or recorded |
| kagent discovery | `RemoteMCPServer/mcpg-readonly-spike` became `Accepted=True` |
| Agent | `mcpg-readonly-schema-spike-agent` became `Accepted=True`, `Ready=True` |
| Conversational proof | A2A terminal response began `MCPG_SCHEMA_SPIKE_REPLY_OK` and returned the synthetic view's 13 columns |
| Tool history | Only `list_tables` and `describe_table` returned successful function responses |

## Important finding

MCPg's server-level discovery surface is broad even when its access mode is
read-only: it includes schema, role, lock, diagnostic, vector, and other
read-only database inspection tools. Read-only does **not** mean low data
exposure.

The POC therefore mounted exactly three tools on the kagent Agent:
`list_schemas`, `list_tables`, and `describe_table`. The observed run used only
two of them. Do not give a work agent the full discovered catalogue. Also make
the Agent Gateway route and NetworkPolicy the only accessible path; do not
treat an in-cluster Service as a sufficient authorization boundary.

## Lab-only exception

The synthetic in-cluster PostgreSQL fixture uses a non-TLS DSN. The spike sets
`MCPG_ALLOW_INSECURE_TLS=true` only so it can reach that fixture. A work
deployment must remove that variable and require `sslmode=require` or stronger
on the supplied PostgreSQL connection string.

## Reproduce / inspect

```bash
kubectl --context {{CONTEXT}} apply -f mcpg-readonly-spike.yaml
kubectl --context {{CONTEXT}} -n postgres-dab-mcp-poc rollout status deployment/mcpg-readonly-spike --timeout=180s
kubectl --context {{CONTEXT}} -n kagent wait --for=condition=Accepted=True remotemcpserver/mcpg-readonly-spike --timeout=180s
kubectl --context {{CONTEXT}} -n kagent wait --for=condition=Ready=True agent/mcpg-readonly-schema-spike-agent --timeout=180s
```

Use the repository `scripts/kagent-a2a-invoke.sh` helper for the A2A call and
save its raw receipt outside Git. Cleanup is explicit:

```bash
kubectl --context {{CONTEXT}} delete -f mcpg-readonly-spike.yaml --ignore-not-found
```

## Work decision

MCPg is now a valid **candidate** for a narrow work POC, not an automatic
production choice. Before adoption: mirror the pinned digest internally, run
image/SBOM/vulnerability review, remove the insecure TLS exception, configure
an approved database reader role, validate exact Agent Gateway routing/auth,
and allowlist only the agreed tools.
