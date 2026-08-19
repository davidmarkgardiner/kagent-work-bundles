# MCPg v0.7.1 — work lift-and-shift bundle

This is the single current work bundle for the proven MCPg shape:

```text
kagent schema Agent
  -> RemoteMCPServer (Streamable HTTP)
  -> Agent Gateway allowlist
  -> MCPg v0.7.1 at /mcp
  -> PostgreSQL reader connection
```

It contains **no CrystalDBA image, `--access-mode=restricted` flag, SSE
transport, `DATABASE_URI`, or generic `execute_sql` Agent.** Do not combine it
with older PostgreSQL MCP examples elsewhere in the repository.

## What was proven in the HomeLab

| Capability | Status |
|---|---|
| MCPg discovers and serves `list_schemas`, `list_tables`, and `describe_table` over Streamable HTTP `/mcp` | **Verified** |
| kagent `RemoteMCPServer` discovers those MCPg tools and a schema Agent calls them conversationally | **Verified** |
| MCPg has no database credential inside the Agent | **Verified design and HomeLab configuration** |
| Agent Gateway route and allowlist works for a bounded FastMCP route | **Verified separately** |
| This exact MCPg work overlay works against the installed work CRDs and work PostgreSQL | **Requires validation** |
| UAMI/Entra authentication to work PostgreSQL | **Requires validation** |

## Files

| File | Purpose |
|---|---|
| [mcpg-postgres-mcp.yaml](mcpg-postgres-mcp.yaml) | MCPg v0.7.1 Deployment and Service. Environment variables only; no CLI arguments. |
| [agentgateway-route.yaml](agentgateway-route.yaml) | Agent Gateway MCP backend, `/mcp` route, schema-tool allowlist, rate limit, and timeout. |
| [kagent-agent.yaml](kagent-agent.yaml) | Streamable HTTP `RemoteMCPServer` plus schema-only kagent Agent. |
| [mcpg-read-query-profile/](mcpg-read-query-profile/) | Optional SELECT-only extension for approved inventory views; adds MCPg `run_select`, not write access. |
| [postgres-inventory-data-contract-skill/](postgres-inventory-data-contract-skill/) | Versioned skill-image example and replacement Agent for approved PostgreSQL inventory context. |
| [mcp-networkpolicy.yaml](mcp-networkpolicy.yaml) | Gateway-only steady-state ingress policy. |
| [direct-mcp-probe.yaml](direct-mcp-probe.yaml) | Temporary direct MCPg discovery probe. |
| [gateway-mcp-probe.yaml](gateway-mcp-probe.yaml) | Temporary Agent Gateway discovery probe. |
| [MCPG-WORK-VARIABLES.md](MCPG-WORK-VARIABLES.md) | Complete private-overlay variable contract. |
| [OUTSIDE-IN-VALIDATION-CHECKLIST.md](OUTSIDE-IN-VALIDATION-CHECKLIST.md) | Deploy/test order and pass criteria. |

## Private-overlay inputs

Obtain these before rendering:

```text
POSTGRES_USERNAME
POSTGRES_PASSWORD
POSTGRES_ENDPOINT
POSTGRES_DATABASE
MCPG_IMAGE
POSTGRES_MCP_SECRET_NAME
DATA_MCP_NAMESPACE
KAGENT_NAMESPACE
KAGENT_MODEL_CONFIG
AGENTGATEWAY_NAMESPACE
AGENTGATEWAY_NAME
AGENTGATEWAY_SERVICE
```

The Secret must contain only `postgres-url`, constructed outside Git with TLS,
for example:

```text
postgresql://{{POSTGRES_USERNAME}}:{{POSTGRES_PASSWORD}}@{{POSTGRES_ENDPOINT}}/{{POSTGRES_DATABASE}}?sslmode=require
```

MCPg receives that key as `MCPG_DATABASE_URL`. kagent and Agent Gateway do not
receive it. The work deployment must not set `MCPG_ALLOW_INSECURE_TLS`.

## Render and deploy

1. Make a private overlay and replace the ConfigMap literals in
   [kustomization.yaml](kustomization.yaml), particularly `mcpgImage` with the
   approved internal **digest-pinned** MCPg v0.7.1 mirror.
2. Deliver `postgres-url` through the approved secret system; do not create a
   literal Secret from this repository.
3. Follow the [outside-in validation checklist](OUTSIDE-IN-VALIDATION-CHECKLIST.md).
4. After direct and Gateway probes pass, apply the steady-state bundle:

   ```sh
   kubectl --context {{WORK_KUBE_CONTEXT}} apply -k .
   ```

The Kustomize package deliberately excludes both temporary probes.

## Non-negotiable guardrails

- `MCPG_ACCESS_MODE=read-only`; database grants and approved views remain the
  real data boundary.
- The first Agent mounts only `list_schemas`, `list_tables`, and
  `describe_table`.
- The Gateway policy repeats exactly that allowlist.
- Do not expose an arbitrary SQL/query tool until data owner approval, masking,
  model-egress review, and explicit negative tests are complete.
- Run server-side dry-runs against the installed kagent and Agent Gateway CRDs
  before applying. Gateway schemas vary by release.

For an approved namespace count or similar read question, use the optional
[read-query profile](mcpg-read-query-profile/). It adds MCPg's `run_select`
tool while retaining `MCPG_ACCESS_MODE=read-only` and a database role that can
only `SELECT` approved views. Do not switch to MCPg `restricted` mode merely
to run a count.

The optional data-contract skill improves the Agent's understanding of
approved views and business meanings without widening its access. Use
[postgres-inventory-data-contract-skill/](postgres-inventory-data-contract-skill/)
after the read-query profile has passed validation. Its workload-identity
decision record explains why MCPg is not yet a passwordless Azure PostgreSQL
candidate.
