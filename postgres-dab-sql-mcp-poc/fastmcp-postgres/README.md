# FastMCP PostgreSQL adapter image

This is the custom, bounded alternative to a generic PostgreSQL MCP. It turns
four approved Python functions into Streamable HTTP MCP tools at `/mcp`.
It deliberately contains no `execute_sql` tool.

## Local package smoke

```sh
docker build -t fastmcp-postgres-poc:0.1.0 .
docker run --rm --entrypoint python fastmcp-postgres-poc:0.1.0 \
  -c 'import fastmcp, psycopg; print(fastmcp.__version__, psycopg.__version__)'
```

The 2026-08-15 HomeLab proof built image ID
`sha256:773e01a4411f3599227ec8665e1694ec466e4c21267a229adc6c3951168b6adb`
and confirmed MCP initialization and discovery of all four tools. It is a
local image ID, not a registry digest and not an approved production artifact.

## Work image-release contract

The work CI pipeline, not a developer laptop, must:

1. Build from this directory after replacing/confirming the approved base-image
   digest and generating a complete transitive dependency lock with hashes.
2. Run unit, protocol, vulnerability, licence, and secret scans.
3. Push to the approved internal registry.
4. Sign the immutable registry digest with the organisation's approved signing
   identity, then attach SBOM/provenance as required by platform policy.
5. Deploy only the signed, digest-pinned image, for example:

   ```text
   {{INTERNAL_REGISTRY}}/platform/fastmcp-postgres@sha256:{{IMAGE_DIGEST}}
   ```

No signing identity, registry, private endpoint, database username, or password
is committed in this public repository.

## Database-authentication boundary

The container needs only `POSTGRES_CONNECTION_STRING`, injected from an
environment-owned Secret. The kagent Agent and `RemoteMCPServer` must never
receive it. The synthetic HomeLab proof used a database reader/password; the
target work authentication is **unknown** until the database team confirms its
username/password or Microsoft Entra token path. If Entra/UAMI is required,
add and test a narrow token-acquisition adapter before claiming readiness.
