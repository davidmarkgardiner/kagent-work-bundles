# PostgreSQL + pgvector data MCP HomeLab POC

Status: **live bounded PostgreSQL path PASS; official Microsoft DAB experiment
PARTIAL.** This is a non-production HomeLab proof using synthetic compliance
data. It is not an Amazon RDS connection, a production-data proof, or a claim
that pgvector itself is exposed to the agent.

## What passed live

```text
conversational request
  -> kagent Agent
  -> explicit two-tool RemoteMCPServer binding
  -> bounded Streamable HTTP PostgreSQL MCP adapter
  -> PostgreSQL + pgvector synthetic data
  -> concise answer
```

The live answer to “How many open compliance findings are high severity or
above?” was **2**. The Agent first called
`get_compliance_data_product_details`, then
`get_open_high_severity_compliance_findings`; both tool responses had
`isError:false`.

The database proof also confirmed:

- PostgreSQL `vector` extension version `0.8.6` was installed;
- an HNSW vector index existed on the synthetic source table; and
- the read-only database role could see only the curated summary view.

The Agent has no database credentials, arbitrary SQL, write, raw-table, or
vector-search tool. The adapter alone reads a pre-created lab-only read-only
connection Secret. `automountServiceAccountToken: false` is set on all POC
workloads.

## What this means for RDS

Yes: the original Trino fallback used SQL, but this parallel POC proves the
same kagent/MCP conversational pattern against **PostgreSQL**, with pgvector
installed. Amazon RDS for PostgreSQL supports pgvector on supported engine
versions; the exact engine/extension version must be confirmed in the target
RDS instance before work starts.

AWS maintains the version-specific extension matrix in its
[RDS for PostgreSQL extension documentation](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

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
POSTGRES_SYNTHETIC_QUERY_OK count=2
REMOTE_MCP_DISCOVERY_OK
KAGENT_AGENT_READY_OK
A2A_TWO_TOOL_CALLS_OK
A2A_CONVERSATIONAL_RESPONSE_OK
VERIFY_PASS
```

The checked-in [live A2A receipt](evidence/A2A-CONVERSATIONAL-RECEIPT-2026-08-12.json)
and [run record](evidence/POC-RUN-2026-08-12.md) are deliberately trimmed to
synthetic facts and contain no connection material.

The runtime package install in the custom adapter is a HomeLab convenience.
For an office/RDS POC, build it in approved CI, scan/sign it, pin the digest,
and mirror it internally. Use private connectivity/TLS, a dedicated RDS
read-only role, secretless or short-lived identity where supported, audit, and
one synthetic/masked view. Never put RDS credentials in an Agent manifest.

## Cleanup

```sh
sh work-agent-bundles/postgres-dab-sql-mcp-poc/scripts/teardown.sh red
```
