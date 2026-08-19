# MCPg password-bundle read-query profile

Use this optional overlay when the schema-only MCPg profile is working and the
data owner has approved one or more PostgreSQL views for conversational
read-only queries.

It changes only two things:

1. adds MCPg's `run_select` to the Agent Gateway allowlist; and
2. adds `postgres-inventory-read-query-agent`, which mounts schema tools plus
   `run_select`.

It does **not** change `MCPG_ACCESS_MODE=read-only`, grant database writes, or
expose `run_write`, DDL, shell, maintenance, export, or arbitrary unrestricted
tools. A count query is a `SELECT` operation and belongs in this profile.

## Required database boundary

The MCPg database principal must have only `CONNECT`, schema `USAGE`, and
`SELECT` on owner-approved views. Do not grant it table access merely because a
count query is required. For example, the database owner can provide a
namespace inventory view and permit:

```sql
SELECT count(*) AS namespace_count FROM approved_namespace_inventory;
```

The view name is illustrative; use the work-approved view, not this literal.

## Deploy

The parent `postgres-mcpg-password` Kustomize package remains the schema-only
base. Render these two files with the same private values, then apply them
after that base has passed its source-first checks:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_DIR}}/agentgateway-read-query-policy.yaml \
  -f {{PRIVATE_RENDERED_DIR}}/read-query-agent.yaml
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_DIR}}/agentgateway-read-query-policy.yaml \
  -f {{PRIVATE_RENDERED_DIR}}/read-query-agent.yaml
```

Then wait for `postgres-inventory-read-query-agent`, inspect
`RemoteMCPServer.status.discoveredTools`, and record one owner-approved count
query plus the A2A receipt. See the parent
[outside-in validation checklist](../OUTSIDE-IN-VALIDATION-CHECKLIST.md).

## Do not use this for writes

MCPg `restricted` mode enables write tools. That is a separate, higher-risk
change requiring a dedicated database role, tool allowlist, approval workflow,
rollback, and negative tests. It is intentionally not included in this bundle.
