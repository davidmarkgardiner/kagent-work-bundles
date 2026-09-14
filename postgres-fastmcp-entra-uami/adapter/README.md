# FastMCP PostgreSQL dual-authentication adapter

This one adapter supports an initial PostgreSQL username/password deployment
and a later AKS Workload Identity/UAMI deployment without changing its MCP
tools or query implementations.

It deliberately exposes three bounded, read-only tools, not arbitrary SQL:

1. `get_inventory_data_product_details()`
2. `get_namespace_count()`
3. `get_namespace_summary(namespace_name)`

Every database result is wrapped in a fail-closed model-context budget. The
adapter fetches at most 51 rows, returns at most 50 rows, limits each cell to
512 characters, limits the complete result to 32 KiB, and marks truncation in
the response. Environment values may lower these limits but cannot raise the
hard ceilings of 100 rows, 2,048 characters per cell, or 64 KiB per response.
Queries also run in a read-only transaction with a five-second statement
timeout whose hard ceiling is 30 seconds. Do not treat pagination as an export
mechanism; create an approved out-of-band export when full data is required.

The optional controls are `MCP_MAX_ROWS`, `MCP_MAX_RESPONSE_BYTES`,
`MCP_MAX_CELL_CHARS`, and `POSTGRES_STATEMENT_TIMEOUT_MS`.

Use [`../tests/local-k8s/`](../tests/local-k8s/) to prove the compiled adapter
against a disposable 5,000-row TLS PostgreSQL fixture in a local kind cluster.

Set exactly one supported `POSTGRES_AUTH_MODE`:

- `password`: `psycopg.connect` receives `POSTGRES_USER` and
  `POSTGRES_PASSWORD` from Secret-backed environment variables.
- `entra`: `DefaultAzureCredential` and Microsoft’s
  `azure-postgresql-auth` connection class obtain fresh UAMI tokens.

```text
kagent -> Agent Gateway -> FastMCP adapter -> password Secret -> PostgreSQL
                                           or
                                           -> Workload Identity/UAMI -> Entra token -> PostgreSQL
```

## Private deployment inputs

```text
FASTMCP_IMAGE                # same approved digest-pinned image for both paths
POSTGRES_AUTH_MODE           # password or entra
POSTGRES_HOST                # Azure Flexible Server FQDN
POSTGRES_DATABASE            # approved database name
APPROVED_VIEW                # lower-case schema-qualified approved view
DENIED_BASE_TABLE            # lower-case schema-qualified denial-test table
```

For password mode, inject only the separate username and password Secret keys;
never store them in Git or a ConfigMap. For Entra mode, map the UAMI to a
PostgreSQL role. In both modes grant only `CONNECT`, schema `USAGE`, and
`SELECT` on the approved view. Never add a generic query tool.

After the Pod is Ready, run `python /app/verify_live.py` inside it. The verifier
prints markers only: it proves authentication, TLS connectivity, approved
view access, absence of base-table and view-write privileges, and a fresh
second connection. It does not print tokens, passwords, rows, database
identities, or environment-specific object names. Then render
`agentgateway-kagent.yaml.template`, wait for its resources to be accepted and
ready. Finally, retain the database and A2A gates in one durable receipt run:

```bash
./work-agent-bundles/postgres-fastmcp-entra-uami/adapter/verify-live.sh \
  {{AKS_CONTEXT}} {{PRIVATE_RECEIPT_PATH}}
```

The script is read-only. It does not render or apply the templates, create
Azure resources, or print environment identifiers.

The recovered local package checkpoint and its remaining live boundaries are
recorded in
[`../evidence/FASTMCP-ENTRA-LOCAL-RECOVERY-2026-08-19.md`](../evidence/FASTMCP-ENTRA-LOCAL-RECOVERY-2026-08-19.md).

The subsequent live AKS/UAMI/PostgreSQL proof is recorded in
[`../evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md`](../evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md).
