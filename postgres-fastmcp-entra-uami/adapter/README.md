# FastMCP PostgreSQL Entra/UAMI adapter

This is the small replacement for MCPg when Azure Database for PostgreSQL must
be accessed using AKS Workload Identity rather than a database password.

It deliberately exposes two typed, read-only tools, not arbitrary SQL:

1. `get_namespace_count()`
2. `get_namespace_summary(namespace_name)`

The adapter uses `DefaultAzureCredential` and Microsoft’s
`azure-postgresql-auth` psycopg3 connection class. The Pod gets no PostgreSQL
password or connection-string Secret.

```text
kagent -> Agent Gateway -> FastMCP adapter -> AKS workload identity
                                           -> Azure Entra token
                                           -> Azure Database for PostgreSQL
```

## Private deployment inputs

```text
FASTMCP_ENTRA_IMAGE          # approved internal digest-pinned image
UAMI_CLIENT_ID               # assigned to the ServiceAccount annotation
POSTGRES_HOST                # Azure Flexible Server FQDN
POSTGRES_DATABASE            # approved database name
APPROVED_VIEW                # lower-case schema-qualified approved view
DENIED_BASE_TABLE            # lower-case schema-qualified denial-test table
```

The database owner must map the UAMI to a PostgreSQL Entra role and grant only
`CONNECT`, schema `USAGE`, and `SELECT` on the approved view.

Do not add a password, `POSTGRES_CONNECTION_STRING`, `PGPASSWORD`, or generic
query tool to this adapter. Build/push the image through the approved work
registry and render `aks-workload-identity.yaml.template` privately.

After the Pod is Ready, run `python /app/verify_live.py` inside it. The verifier
prints markers only: it proves token acquisition, TLS connectivity, approved
view access, absence of base-table and view-write privileges, and a fresh
second Entra-authenticated connection. It does not print tokens, rows, database
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
