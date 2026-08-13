# Kubernetes inventory PostgreSQL MCP POC — live evidence

Date: 2026-08-13

## Verified current capability

The disposable `red` HomeLab POC seeded synthetic Kubernetes namespace and
container-image inventory into PostgreSQL 17 with pgvector `0.8.6`. It created
the HNSW index `container_image_inventory_embedding_hnsw`.

The MCP server discovered exactly these four read-only functions:

```text
get_kubernetes_inventory_data_product_details
get_namespace_workload_summary
get_namespace_container_images
get_image_risk_summary
```

The `postgres-kubernetes-inventory-lab-agent` was `Accepted=True, Ready=True`.
A conversational A2A task first called the metadata function and then called
`get_image_risk_summary` with `namespace_name=payments` and
`severity_min=high`. Both function responses were `isError:false`.

The final answer reported two synthetic images with high or critical findings:
one image with `0 critical / 2 high`, and one with `1 critical / 3 high`.

The verifier emitted:

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

## Not proven

- Azure Database for PostgreSQL Flexible Server, private endpoint/DNS,
  Microsoft Entra authentication, UAMI, AKS Workload Identity, or real schema;
- a real Kubernetes inventory, container registry, vulnerability scanner, or
  data-mesh connection; and
- official Microsoft Data API Builder query execution against this revised
  schema. The prior DAB experiment remains a separately documented partial
  result.
