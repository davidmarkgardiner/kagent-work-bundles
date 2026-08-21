# Pre-built PostgreSQL MCP image spike — live evidence

Date: 2026-08-13

## Verified current capability

The third-party pre-built image `crystaldba/postgres-mcp:latest` started in
`restricted` mode against the disposable synthetic PostgreSQL POC database.
It served MCP over SSE and the kagent `RemoteMCPServer` reached
`Accepted=True`.

kagent discovered these nine tools:

```text
list_schemas
list_objects
get_object_details
explain_query
analyze_workload_indexes
analyze_query_indexes
analyze_db_health
get_top_queries
execute_sql
```

The separate `postgres-prebuilt-mcp-schema-spike-agent` was
`Accepted=True, Ready=True`. A conversational A2A request called
`list_schemas` with `isError:false` and returned the expected synthetic
PostgreSQL schemas.

## Decision

**Suitable as a discovery/compatibility candidate, not selected as the
production data-agent implementation.**

The image is pullable and works with the installed kagent SSE client. However,
even in restricted mode it presents a broad database-operations surface,
including a general `execute_sql` tool. A read-only database role is a useful
second boundary but does not replace an owner-approved function contract.

For the final data-agent route, prefer an existing data-platform MCP that
already exposes the agreed functions. Otherwise retain the thin bounded MCP
adapter, which exposes only the four-to-five approved functions and their
typed variables.

## Not proven

- Azure PostgreSQL/UAMI/AKS Workload Identity authentication;
- the image's long-term maintenance, vulnerability posture, licensing, or
  internal registry approval; and
- that its generic SQL interface meets the data owner's governance policy.

Never deploy the mutable `latest` tag to work. An approved POC would pin a
reviewed digest, scan/sign it, and mirror it into the internal registry.

## Cleanup

The experimental Deployment, Service, RemoteMCPServer, and Agent were removed
from the HomeLab after the evidence was collected. The bounded Kubernetes
inventory POC remains separately deployed.
