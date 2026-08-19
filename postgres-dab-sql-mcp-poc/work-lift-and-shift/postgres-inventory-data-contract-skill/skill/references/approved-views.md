# Approved-view catalogue template

Status: **template only.** Replace all view and column names with the
data-owner-approved work contract before building an image. Do not point the
Agent at base tables merely because they exist in PostgreSQL.

| Data product | Illustrative approved view | Illustrative questions | Minimum result shape |
|---|---|---|---|
| AKS estate | `approved_aks_estate` | Clusters by region, OS, lifecycle state, cluster type | Cluster name, region, OS type, lifecycle state, cluster type |
| Application directory | `approved_uk8s_appdir` | Ownership and stream context for an approved application key | Division, pod, business owner, stream path/source |
| Namespace inventory | `approved_namespace_inventory` | Number of namespaces, workload type by LOB, telemetry coverage | Namespace, owner, workload type, LOB, region, telemetry tags |

## Contract fields to obtain from the data owner

For each approved view, record:

1. exact schema-qualified view name;
2. column names, data types, nullable fields, and freshness timestamp;
3. permitted joins and stable keys;
4. data classification and fields that must never be returned to the model;
5. maximum rows, mandatory filters, and approved aggregations; and
6. database role grants proving the MCP principal can only `SELECT` these
   views.

Do not record connection strings, credentials, private endpoints, tenant IDs,
or production records in this file.
