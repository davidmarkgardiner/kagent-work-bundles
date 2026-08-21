# FastMCP PostgreSQL username/password deployment

Use this directory for the first workplace proof while the UAMI is not ready.
It deploys the same FastMCP image, tools, approved-view queries, Service,
Gateway route, RemoteMCPServer, and Agent as the later UAMI path.

Only the database authentication changes:

```text
FastMCP -> POSTGRES_USER and POSTGRES_PASSWORD from Secret -> TLS PostgreSQL
```

The Pod disables ServiceAccount token automounting. Do not add workload-identity
labels, annotations, a UAMI identifier, a connection string, or literal
credentials to this directory.

## Prerequisites

- the shared adapter image has been built from `../adapter/`, scanned, signed,
  pushed internally, and resolved to an immutable digest;
- the existing PostgreSQL login has only `CONNECT`, schema `USAGE`, and
  `SELECT` on the approved view;
- the same role cannot read the chosen denied base table and cannot write to
  the approved view;
- private DNS, network routing, and TLS are available from the namespace; and
- the approved secret-delivery system has created one Secret in
  `FASTMCP_NAMESPACE` containing the username and password keys.

The default key names in `work-values.env.template` are `username` and
`password`. Change the key-name settings if the existing Secret uses different
keys. The values file contains only the Secret name and key names, never the
credential values.

## Render

```sh
cd work-agent-bundles/postgres-fastmcp-entra-uami/password
cp work-values.env.template work-values.env
${EDITOR:-vi} work-values.env
kubectl kustomize . > {{PRIVATE_PASSWORD_RENDERED_FILE}}
```

Before applying, confirm:

```sh
if grep -n '{{' {{PRIVATE_PASSWORD_RENDERED_FILE}}; then
  echo 'unresolved placeholders remain' >&2
  exit 1
fi
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_PASSWORD_RENDERED_FILE}}
```

Do not print the Secret or rendered environment values as evidence.

## Deploy and verify

Apply the same rendered file that passed server-side dry-run, wait for the
Deployment, then run the shared verifier:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_PASSWORD_RENDERED_FILE}}
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{FASTMCP_NAMESPACE}} \
  rollout status deployment/fastmcp-postgres-entra --timeout=180s

FASTMCP_NAMESPACE={{FASTMCP_NAMESPACE}} \
KAGENT_NAMESPACE={{KAGENT_NAMESPACE}} \
../adapter/verify-live.sh \
  {{WORK_KUBE_CONTEXT}} {{PRIVATE_RECEIPT_PATH}}
```

The in-Pod database verifier must emit:

```text
PASSWORD_SECRET_CONFIGURATION_OK
POSTGRES_TLS_SELECT_ONE_OK
APPROVED_VIEW_SELECT_OK
BASE_TABLE_SELECT_DENIED_OK
APPROVED_VIEW_WRITE_DENIED_OK
FRESH_POSTGRES_CONNECTION_OK
FASTMCP_DATABASE_GATES_PASS
```

The A2A verifier must also prove exact three-tool discovery and successful
calls to `get_inventory_data_product_details` and `get_namespace_count`.

## Later UAMI swap

Do not change the Agent or tools. Complete the root bundle's UAMI prerequisites
and render `kubectl kustomize ..` with its separate ignored values file. Apply
that UAMI rendering over this deployment, then repeat all database, discovery,
and A2A gates before asking the secret owner to remove the password Secret.
