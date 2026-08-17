# MCPg v0.7.1 work variables

This is the private-overlay input contract for the MCPg v0.7.1 YAML in this
folder. The database credential belongs only in the MCPg workload Secret.

## Obtain these first

| Private value | Used by | Required form |
|---|---|---|
| `POSTGRES_USERNAME` | Secret delivery only | dedicated non-human reader |
| `POSTGRES_PASSWORD` | Secret delivery only | secret value; never commit or print |
| `POSTGRES_ENDPOINT` | Secret delivery only | private FQDN and port reachable from AKS |
| `POSTGRES_DATABASE` | Secret delivery only | database name |
| `MCPG_IMAGE` | MCPg Deployment | approved internal MCPg v0.7.1 image pinned by digest |

The secret system creates `{{POSTGRES_MCP_SECRET_NAME}}` with one key,
`postgres-url`, constructed outside Git:

```text
postgresql://{{POSTGRES_USERNAME}}:{{POSTGRES_PASSWORD}}@{{POSTGRES_ENDPOINT}}/{{POSTGRES_DATABASE}}?sslmode=require
```

MCPg consumes that key through `MCPG_DATABASE_URL`. Do not set
`MCPG_ALLOW_INSECURE_TLS` in work.

## Kubernetes and kagent coordinates

| Variable | Purpose |
|---|---|
| `WORK_KUBE_CONTEXT` | command target only; do not put in YAML |
| `DATA_MCP_NAMESPACE` | Secret, MCPg Deployment, Service, and NetworkPolicy namespace |
| `POSTGRES_MCP_SECRET_NAME` | Secret containing only `postgres-url` |
| `KAGENT_NAMESPACE` | `RemoteMCPServer` and Agent namespace |
| `KAGENT_MODEL_CONFIG` | approved existing kagent ModelConfig |
| `AGENTGATEWAY_NAMESPACE` | Agent Gateway namespace |
| `AGENTGATEWAY_NAME` | Gateway resource name |
| `AGENTGATEWAY_SERVICE` | Gateway service/DNS name |
| `PRIVATE_EVIDENCE_DIR` | owner-only A2A receipt and sanitised-log location |

## Fixed MCPg v0.7.1 settings

These are already in [mcpg-postgres-mcp.yaml](mcpg-postgres-mcp.yaml). Do not
replace them with command-line flags.

```yaml
MCPG_ACCESS_MODE: read-only
MCPG_TRANSPORT: streamable-http
MCPG_HTTP_HOST: 0.0.0.0
MCPG_HTTP_PORT: "8000"
MCPG_ENABLE_ANALYTICAL_QUERIES: "false"
MCPG_STATEMENT_TIMEOUT_MS: "10000"
MCPG_LOCK_TIMEOUT_MS: "3000"
MCPG_LOG_LEVEL: WARNING
```

The initial kagent and Gateway allowlist is exactly:

```text
list_schemas
list_tables
describe_table
```

No arbitrary SQL or row-query tool is included in this deployment. Add any
later tool only after approved views, data classification/masking, model-egress
review, and negative tests are complete.
