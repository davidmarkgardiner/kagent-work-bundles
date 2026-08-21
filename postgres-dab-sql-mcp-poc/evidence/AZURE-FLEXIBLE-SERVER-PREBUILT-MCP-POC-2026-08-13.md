# Azure PostgreSQL Flexible Server + pre-built MCP — live POC evidence

Date: 2026-08-13

## Verified current capability

A temporary, minimum-size Azure Database for PostgreSQL Flexible Server was
created in a dedicated deletion-tagged resource group. It had no high
availability or geo-redundant backup, and a temporary firewall rule admitted
only the HomeLab egress address.

The database was seeded with synthetic lower-case representations of the
reported data shape:

| Object | Synthetic purpose |
|---|---|
| `public.aks_estate` | Cluster estate facts: cluster, OS, running state, VM size, owner, type, region |
| `public.uk8s_namespaces` | Namespace metadata: owner, workload type, LOB, environment, tags, CMDB reference |
| `public.uk8s_appdir` | Application-directory metadata: division, pod, business owner, stream fields |
| `public.v_namespace_inventory` | Approved joined namespace/app-directory query surface |

A distinct `mcp_reader` role received `SELECT` only on `aks_estate` and
`v_namespace_inventory`. The pre-built `crystaldba/postgres-mcp` image ran in
restricted mode and connected to the Azure server over TLS. kagent registered
it over SSE, discovered its tools, and a temporary Agent was
`Accepted=True, Ready=True`.

The Agent answered this conversational request:

> Which synthetic namespaces are in the production environment, who owns them,
> and what is their CMDB reference?

It called `list_objects`, `get_object_details`, and `execute_sql`, receiving
successful responses, then returned two expected synthetic rows: `catalogue`
and `payments`, their platform owners, and synthetic CMDB references.

## What this proves

- A pre-built PostgreSQL MCP image can connect from the HomeLab Kubernetes
  cluster to Azure PostgreSQL using a database connection string stored only in
  the MCP workload Secret.
- kagent can discover and call that MCP through `RemoteMCPServer` over SSE.
- A conversational Agent can retrieve data from the approved synthetic view.

## Important boundary

The pre-built image exposes broad tools, including `execute_sql`. The read-only
database grants prevented it from reading non-granted objects or writing, but a
general SQL tool is still not the preferred final data-agent contract. Use this
result to prove connectivity and integration only. The final implementation
should either use an existing governed data API/MCP or expose owner-approved,
typed functions from a thin custom MCP.

## Not proven

- Microsoft Data API Builder execution against Azure PostgreSQL: it was not
  used in this run because the requested route was a pre-built PostgreSQL MCP
  image.
- Microsoft Entra/UAMI/AKS Workload Identity database authentication: this POC
  used a temporary dedicated read-only database username/password.
- Any real database, credentials, data, schema, application, cluster, or
  production network route.

## Cleanup

Immediately after evidence collection, the temporary Agent, RemoteMCPServer,
MCP Deployment/Service, Kubernetes namespace, Secrets, and local temporary
credential files were removed. Azure resource-group deletion was submitted;
Azure deletion is asynchronous and should be checked for terminal completion
before treating all billable resources as gone. Azure may retain service-managed
recovery backup data for its documented period after server deletion.

### Terminal cleanup check

On 2026-08-13, a read-only Azure check returned `false` for the temporary
resource group. This confirms the group no longer exists. Retention of any
service-managed backup remains governed by Azure's documented service policy;
the Azure subscription/platform owner must retain the relevant service record
if formal deletion assurance is required.
