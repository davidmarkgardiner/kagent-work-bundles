# FastMCP PostgreSQL Entra/UAMI bundle — recovered local checkpoint

Date: 2026-08-19
Scope: local/offline package validation only

## Result

**PASS — the recovered adapter builds and its bounded tool contract works
locally.** This does not prove AKS workload identity, Azure PostgreSQL access,
private networking, database grants, token refresh, Agent Gateway routing, or
kagent A2A execution.

## Evidence

- The digest-pinned Python base image built successfully as
  `fastmcp-postgres-entra-poc:local`.
- The runtime reports FastMCP `2.14.3` and psycopg `3.2.12`.
- The container runs as UID/GID `10001:10001`.
- FastMCP registered exactly these tools:
  `get_inventory_data_product_details`, `get_namespace_count`, and
  `get_namespace_summary`.
- Offline contract tests proved the count query targets only
  `public.approved_namespace_inventory` and the namespace lookup uses a bound
  `%s` parameter.
- The workload-identity manifest template passed Kubernetes client-side
  parsing after placeholders were rendered with public-safe dummy values.
- The Agent Gateway, policy, RemoteMCPServer, and Agent template passed
  server-side dry-run against the installed HomeLab CRD versions. This proves
  schema admission only, not runtime routing.
- The image contains a marker-only live verifier for token acquisition, TLS,
  least-privilege database grants, and a fresh Entra-authenticated connection.
- `verify-live.sh` composes those database checks with exact Gateway tool
  discovery, Agent readiness, and a durable A2A receipt.
- The bundle passed `scripts/public-safe-scan.sh`.

FastMCP emitted an Authlib deprecation warning while importing its JWT provider.
It did not fail the build or tests; retain the dependency pin until a deliberate
upgrade is tested.

## Repeat locally

```bash
docker build -t fastmcp-postgres-entra-poc:local \
  work-agent-bundles/postgres-fastmcp-entra-uami/adapter

docker run --rm \
  -e POSTGRES_HOST=postgres.example.invalid \
  -e POSTGRES_DATABASE=synthetic \
  -v "$PWD/work-agent-bundles/postgres-fastmcp-entra-uami/adapter/test_server.py:/app/test_server.py:ro" \
  --entrypoint python fastmcp-postgres-entra-poc:local \
  -m unittest -v test_server.py
```

## Remaining live gates

The five gates in `../references/WHY-NOT-MCPG-FOR-UAMI.md` remained open at
this local checkpoint. The next authorized environment run had to prove passwordless token
acquisition, TLS `SELECT 1`, approved-view access plus base-table/write denial,
fresh-token reconnect, and Gateway/kagent A2A evidence.

The active `red` development cluster was inspected read-only. It is healthy
and has compatible kagent and Agent Gateway CRDs, but it is not the authorized
AKS workload-identity target, so no recovered resources were applied there.
