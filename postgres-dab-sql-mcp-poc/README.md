# PostgreSQL + pgvector Kubernetes inventory MCP HomeLab POC

Status: **live bounded PostgreSQL path PASS; official Microsoft DAB experiment
PARTIAL.** This is a non-production HomeLab proof using synthetic Kubernetes
namespace and container-image inventory
data. It is not an Azure Database for PostgreSQL connection, a production-data
proof, or a claim that pgvector itself is exposed to the agent.

## What passed live

```text
conversational request
  -> kagent Agent
  -> explicit two-tool RemoteMCPServer binding
  -> bounded Streamable HTTP PostgreSQL MCP adapter
  -> PostgreSQL + pgvector synthetic Kubernetes inventory
  -> concise answer
```

The next live proof asks: “Which container images in the `payments` namespace
have high or critical findings?” The Agent must first call
`get_kubernetes_inventory_data_product_details`, then
`get_image_risk_summary(namespace_name="payments", severity_min="high")`.
This proves that the agent passes named variables to a bounded tool rather than
submitting raw SQL.

The database proof also confirmed:

- PostgreSQL `vector` extension version `0.8.6` was installed;
- an HNSW vector index existed on the synthetic image-inventory source table; and
- the read-only database role could see only the curated summary view.

The Agent has no database credentials, arbitrary SQL, write, raw-table, or
vector-search tool. The adapter alone reads a pre-created lab-only read-only
connection Secret. `automountServiceAccountToken: false` is set on all POC
workloads.

## Synthetic Kubernetes data contract

| Data set | Synthetic fields | Purpose |
|---|---|---|
| Namespace inventory | namespace, environment, owner team, workload count, running pod count, observation date | Namespace health/context questions |
| Image inventory | namespace, workload, image repository/tag/digest, high/critical finding counts, scan date | Container-image risk questions |

The MCP exposes only these four read-only functions:

1. `get_kubernetes_inventory_data_product_details()`
2. `get_namespace_workload_summary(namespace_name)`
3. `get_namespace_container_images(namespace_name, limit)`
4. `get_image_risk_summary(namespace_name, severity_min)`

The first three namespace values are synthetic: `payments`, `catalogue`, and
`developer-tools`. The records do not describe the HomeLab cluster.

## What this means for Azure PostgreSQL

Yes: the original Trino fallback used SQL, but this parallel POC proves the
same kagent/MCP conversational pattern against **PostgreSQL**, with pgvector
installed. Azure Database for PostgreSQL Flexible Server supports pgvector; the
exact server version, extension version, and approved index/query pattern must
be confirmed in the target environment before work starts.

Microsoft documents pgvector support and vector-query patterns for
[Azure Database for PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-develop-with-langchain).

pgvector is a database capability, not an automatic agent permission. Keep
vector similarity search behind a separate approved view or parameterised MCP
tool. The first compliance POC intentionally exposes only a normal governed
summary query.

## Official Microsoft SQL MCP result

The POC also tested Microsoft’s official Data API Builder (DAB) SQL MCP image
`2.0.9` against the same PostgreSQL service. It was accepted by kagent and
discovered `describe_entities`, `read_records`, and `aggregate_records`.
However, this live combination is **not a pass**:

- `read_records` failed with DAB/Npgsql: `Attempt to read a position in the
  column which has already been read`;
- DAB reported its aggregate tool unsupported for PostgreSQL; and
- the Agent properly declined to fabricate a result.

The DAB manifests remain in this folder as a reproducible supplier-support
experiment, but are disabled by default in `deploy.sh`. Set
`WITH_DAB_EXPERIMENT=true` only to reproduce the partial result after capacity
has been confirmed. Do not use it as the production candidate until Microsoft
confirms a fixed supported DAB/PostgreSQL release.

Microsoft documents DAB SQL MCP as supporting PostgreSQL through configured
entities and says it deliberately avoids arbitrary NL2SQL. See the
[official SQL MCP overview](https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/overview)
and [runtime tool controls](https://learn.microsoft.com/en-us/azure/data-api-builder/configuration/runtime).

## Run and verify

```sh
sh work-agent-bundles/postgres-dab-sql-mcp-poc/scripts/deploy.sh red
sh work-agent-bundles/postgres-dab-sql-mcp-poc/scripts/verify.sh red
```

Expected markers:

```text
POSTGRES_SEED_JOB_COMPLETED_OK
PGVECTOR_EXTENSION_AND_INDEX_OK
POSTGRES_SYNTHETIC_KUBERNETES_QUERY_OK namespace=payments count=2
REMOTE_MCP_DISCOVERY_OK
KAGENT_AGENT_READY_OK
A2A_PARAMETERISED_TOOL_CALLS_OK
A2A_CONVERSATIONAL_RESPONSE_OK
VERIFY_PASS
```

The checked-in [Kubernetes-inventory A2A receipt](evidence/KUBERNETES-INVENTORY-A2A-RECEIPT-2026-08-13.json)
and [run record](evidence/KUBERNETES-INVENTORY-POC-RUN-2026-08-13.md) are
deliberately trimmed to synthetic facts and contain no connection material.

The earlier compliance-shaped receipts remain historical evidence for the
initial PostgreSQL connectivity exercise; the current manifests and verifier
are the Kubernetes-inventory POC described above.

## Custom FastMCP proof — re-verified 2026-08-14

This bundle also contains the custom-MCP shape suitable for the work use case:
ordinary Python functions exposed through FastMCP, each with typed inputs,
parameterised PostgreSQL queries, and a narrow result contract. It is not a
generic SQL endpoint. The Agent has no database credential and no arbitrary
query tool.

The HomeLab proof was re-run on 2026-08-14 against the live synthetic
PostgreSQL fixture. The verifier passed all eight markers and a fresh kagent
A2A request produced a successful answer after calling the metadata and
parameterised risk-summary tools. See the
[FastMCP re-verification record](evidence/FASTMCP-POSTGRES-POC-REVERIFICATION-2026-08-14.md)
and the [trimmed A2A receipt](evidence/FASTMCP-KUBERNETES-INVENTORY-A2A-RECEIPT-2026-08-14.json).

For work, turn this adapter into an approved, scanned, signed, digest-pinned
image rather than installing Python packages at container startup. Replace the
synthetic queries only with owner-approved views and typed business questions.

## Packaged FastMCP image and Agent Gateway route — verified 2026-08-15

The adapter is now available as a Docker build context in
[fastmcp-postgres/](fastmcp-postgres/), with a non-root runtime and build-time
dependency installation. A local package protocol smoke passed after exposing
and fixing one missing direct dependency. A separate HomeLab Agent Gateway
route server-dry-run, policy attachment, tool discovery, Agent readiness, and
conversational A2A call also passed.

The route proof uses the existing synthetic FastMCP fixture, not the local
image; it demonstrates the installed Gateway CRD shape and four-tool policy,
not registry delivery. The production-template Deployment is
[fastmcp-postgres-image.yaml](fastmcp-postgres-image.yaml). See the
[package and Gateway evidence](evidence/FASTMCP-PACKAGE-AND-AGENTGATEWAY-2026-08-15.md)
for the exact boundaries and remaining work authentication, registry-signing,
private-network, NetworkPolicy, and data-governance gates.

## Pre-built PostgreSQL MCP image spike

A separate, disposable compatibility spike proved that a pre-built third-party
PostgreSQL MCP image can run in restricted mode, expose SSE to kagent, and be
called by a read-only schema agent. It discovered nine tools, including a
general `execute_sql` capability. This makes it useful for schema discovery,
but too broad to select as the final governed data-agent interface without
further owner-approved restrictions. See the [spike evidence](evidence/PREBUILT-POSTGRES-MCP-SPIKE-2026-08-13.md) and
[isolated manifest](prebuilt-postgres-mcp-spike.yaml).

## MCPg GHCR spike — verified 2026-08-13

The newer pre-built `ghcr.io/devopam/mcpg` image was separately proven against
the same synthetic PostgreSQL fixture over Streamable HTTP. kagent discovered
the server and a schema-only Agent used only schema tools. This is a stronger
short-term candidate than the older CrystalDBA image, but MCPg's broad
read-only discovery surface still requires explicit agent/gateway tool
allowlists. See the [MCPg live evidence](evidence/MCPG-GHCR-READONLY-SPIKE-2026-08-13.md)
and [disposable manifest](mcpg-readonly-spike.yaml).

MCPg read-only mode has also proved capable of a bounded `run_select` namespace
count; ordinary inventory questions do not need database write access. The
optional work [read-query profile](work-lift-and-shift/mcpg-read-query-profile/)
adds only `run_select` to the Agent Gateway and Agent allowlists. See the
[read-query evidence](evidence/MCPG-READ-QUERY-POC-2026-08-18.md).

The work lift-and-shift bundle now also has a
[PostgreSQL inventory data-contract skill image example](work-lift-and-shift/postgres-inventory-data-contract-skill/).
It gives a read-query Agent approved-view and query guidance without widening
tool or database permissions. Its [workload-identity decision](work-lift-and-shift/postgres-inventory-data-contract-skill/WORKLOAD-IDENTITY-DECISION.md)
records that the current MCPg image is not a verified passwordless Entra/UAMI
database client; use a small FastMCP adapter for that path.

The HomeLab also live-proved the kagent skill runtime path through a Git-backed
skill source: initialisation completed, the Agent called MCPg `run_select`, and
its response followed the skill's standard format. See the
[skill-runtime evidence](evidence/MCPG-DATA-CONTRACT-SKILL-RUNTIME-POC-2026-08-19.md).
The final work **image-pull** path still needs an ACR/registry validation.

## Azure PostgreSQL live connectivity proof

A short-lived Azure Database for PostgreSQL Flexible Server proof subsequently
used the same pre-built MCP image, synthetic lower-case estate/namespace/appdir
tables, and a dedicated read-only database role. The Agent successfully
retrieved two synthetic production namespace records through the MCP. The
database and Kubernetes resources were deleted immediately after the run; see
the [Azure live evidence](evidence/AZURE-FLEXIBLE-SERVER-PREBUILT-MCP-POC-2026-08-13.md).

The runtime package install in the custom adapter is a HomeLab convenience.
For an office/Azure PostgreSQL POC, build it in approved CI, scan/sign it, pin
the digest, and mirror it internally. Use private connectivity/TLS, a dedicated
Microsoft Entra-backed read-only database role, AKS Workload Identity where
approved, audit, and one synthetic/masked view. Never put database credentials
or access tokens in an Agent manifest.

## Work lift-and-shift bundle

The [work-lift-and-shift](work-lift-and-shift/) folder is now the reusable
MCPg v0.7.1 Azure/AKS handoff: a digest-pinned MCPg deployment, a
Streamable-HTTP gateway-fronted kagent schema binding, password-bootstrap and
later Workload Identity decision points, verification gates, and an
independent-review prompt. It deliberately makes no claim that the exact work
Agent Gateway route, work PostgreSQL authentication, or private network path
has already been live-proven.

## Cleanup

```sh
sh work-agent-bundles/postgres-dab-sql-mcp-poc/scripts/teardown.sh red
```
