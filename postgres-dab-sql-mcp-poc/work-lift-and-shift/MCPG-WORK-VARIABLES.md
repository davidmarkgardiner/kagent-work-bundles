# MCPg work deployment variables

This is the variable contract for the **current MCPg GHCR proof path**. It is
the hand-off input for the work agent that will convert the older
CrystalDBA/SSE templates in this folder to MCPg/Streamable HTTP. Do not mix
the two transports or tool catalogues in one deployment.

The database credential belongs only in the MCP workload Secret. Neither the
kagent Agent nor `RemoteMCPServer` receives a connection string, password, or
database token.

## The four values to obtain first

| Private value | Used by | Required form | Notes |
|---|---|---|---|
| `POSTGRES_USERNAME` | Secret delivery only | dedicated non-human reader | Must have `CONNECT`, schema `USAGE`, and `SELECT` only on approved views. |
| `POSTGRES_PASSWORD` | Secret delivery only | secret value | Never commit, echo, put in an Agent prompt, or attach to evidence. |
| `POSTGRES_ENDPOINT` | Secret delivery only | private FQDN and port | Confirm AKS DNS and TCP reachability before deploying the Agent. |
| `MCPG_IMAGE` | MCP Deployment | approved internal, digest-pinned mirror | Source proven in the HomeLab: `ghcr.io/devopam/mcpg@sha256:f16f97f667832b79ca496f9cbae8a0485ab1fb59beb32a158db4af3da4ada1d9`. Work should scan/sign and mirror it, for example `{{INTERNAL_REGISTRY}}/third-party/mcpg@sha256:{{IMAGE_DIGEST}}`. |

Also obtain `POSTGRES_DATABASE` unless the database team has supplied an
approved full connection URI through the secret-delivery system. The private
secret must materialise one key, `postgres-url`, constructed outside Git:

```text
postgresql://{{POSTGRES_USERNAME}}:{{POSTGRES_PASSWORD}}@{{POSTGRES_ENDPOINT}}/{{POSTGRES_DATABASE}}?sslmode=require
```

The MCPg container consumes that key as `MCPG_DATABASE_URL`. Do **not** use
the HomeLab-only `MCPG_ALLOW_INSECURE_TLS=true` setting in work.

## Kubernetes, kagent, and Agent Gateway coordinates

| Variable | Example placeholder | Why the work overlay needs it |
|---|---|---|
| `WORK_KUBE_CONTEXT` | `{{WORK_KUBE_CONTEXT}}` | Commands and server-side dry-runs only; never stored in a manifest. |
| `DATA_MCP_NAMESPACE` | `{{DATA_MCP_NAMESPACE}}` | Namespace for the Secret, MCP Deployment, Service, and NetworkPolicy. |
| `POSTGRES_MCP_SECRET_NAME` | `{{POSTGRES_MCP_SECRET_NAME}}` | Name of the Secret that contains only `postgres-url`. |
| `KAGENT_NAMESPACE` | `{{KAGENT_NAMESPACE}}` | Namespace containing kagent `RemoteMCPServer` and Agent CRs. |
| `KAGENT_MODEL_CONFIG` | `{{KAGENT_MODEL_CONFIG}}` | Existing approved kagent `ModelConfig`; its model-egress policy must permit the approved view data. |
| `AGENTGATEWAY_NAMESPACE` | `{{AGENTGATEWAY_NAMESPACE}}` | Namespace hosting Agent Gateway. |
| `AGENTGATEWAY_NAME` | `{{AGENTGATEWAY_NAME}}` | Installed Gateway resource name used by route/policy objects. |
| `AGENTGATEWAY_SERVICE` | `{{AGENTGATEWAY_SERVICE}}` | Gateway Service/DNS name for the `RemoteMCPServer` route. |
| `PRIVATE_EVIDENCE_DIR` | `{{PRIVATE_EVIDENCE_DIR}}` | Owner-only destination for A2A receipts and sanitised logs; never a repository path. |

No model-provider credential is injected into MCPg. kagent obtains model
access through the already-approved `ModelConfig` and Agent Gateway setup.

## Fixed first-POC settings (do not make these environment variables)

The work agent should keep these controlled values in the MCP Deployment:

```yaml
env:
  - name: MCPG_DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: {{POSTGRES_MCP_SECRET_NAME}}
        key: postgres-url
  - name: MCPG_ACCESS_MODE
    value: read-only
  - name: MCPG_TRANSPORT
    value: streamable-http
  - name: MCPG_HTTP_HOST
    value: 0.0.0.0
  - name: MCPG_HTTP_PORT
    value: "8000"
  - name: MCPG_ENABLE_ANALYTICAL_QUERIES
    value: "false"
  - name: MCPG_STATEMENT_TIMEOUT_MS
    value: "10000"
  - name: MCPG_LOCK_TIMEOUT_MS
    value: "3000"
  - name: MCPG_LOG_LEVEL
    value: WARNING
```

The first Agent and Agent Gateway allowlist must contain only these schema
discovery tools:

```text
list_schemas
list_tables
describe_table
```

Do not enable a general query tool until approved views, data classification,
model-egress approval, and negative tests are complete.

## Required template conversion

The currently checked-in `prebuilt-postgres-mcp.yaml`, `kagent-agent.yaml`,
probes, and validation checklist are a legacy CrystalDBA/SSE shape. The work
agent must make this explicit MCPg conversion before `kubectl apply -k`:

| Legacy template element | MCPg replacement |
|---|---|
| `crystaldba/postgres-mcp` | `{{MCPG_IMAGE}}` internal digest-pinned mirror |
| `DATABASE_URI` | `MCPG_DATABASE_URL` from `postgres-url` |
| `--access-mode=restricted --transport=sse` | MCPg environment values above |
| MCP path `/sse`, protocol `SSE` | path `/mcp`, protocol `STREAMABLE_HTTP` |
| `list_objects`, `get_object_details`, `execute_sql` | `list_schemas`, `list_tables`, `describe_table` for the first proof |

Keep the existing non-root security context, resource requests/limits, and
NetworkPolicy. The work agent must server-dry-run the converted manifests
against the installed kagent and Agent Gateway CRDs; Agent Gateway schema
compatibility is not inferred from the HomeLab proof.

## Minimum source-first test order

1. Secret exists with the `postgres-url` key; do not decode it.
2. Private endpoint DNS, TCP/5432, CA validation, and reader role work from a
   disposable AKS client.
3. MCPg Deployment rolls out with the digest-pinned image and no database/TLS
   errors in sanitised logs.
4. Direct MCP registration discovers tools through `http://<service>:8000/mcp`.
5. Agent Gateway route discovers the same approved tools and the NetworkPolicy
   prevents direct bypass at steady state.
6. The kagent schema Agent is `Accepted=True`, `Ready=True`, then records one
   A2A receipt using only the three allowlisted tools.

See [MCPG-GHCR-READONLY-SPIKE-2026-08-13.md](../evidence/MCPG-GHCR-READONLY-SPIKE-2026-08-13.md)
for the HomeLab evidence and [OUTSIDE-IN-VALIDATION-CHECKLIST.md](OUTSIDE-IN-VALIDATION-CHECKLIST.md)
for the legacy checklist that must be converted together with the YAML.
