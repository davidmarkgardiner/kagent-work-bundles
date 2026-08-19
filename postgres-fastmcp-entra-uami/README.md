# FastMCP + Azure PostgreSQL UAMI work bundle

Use this path when the database team requires Microsoft Entra authentication
through AKS Workload Identity. Do not try to place a short-lived Entra token in
`MCPG_DATABASE_URL`; use the bounded FastMCP adapter instead.

This is a self-contained work bundle. Its deployable source is
[`adapter/`](adapter/), and its live sanitized proof is
[`evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md`](evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md).
Do not mix it with the separate MCPg username/password bundle at
`../postgres-mcpg-password/`.

Run `scripts/verify-bundle.sh` before handoff. It fails if password, DSN Secret,
or MCPg authentication content appears in this UAMI bundle's deployable files.

For workplace rendering, copy `work-values.env.template` to the ignored
`work-values.env`, replace every placeholder with values checked against the
current environment, and use this directory as the Kustomize target. The
same values file carries the database-team SQL inputs so the client ID, object
ID, role, schema, view, and denial-test table can be cross-checked in one place.
The rendered ConfigMap contains coordinates and IDs but no credential or token.

## Proven architecture

```text
kagent -> Agent Gateway -> FastMCP Service
                           -> AKS Workload Identity token projection
                           -> UAMI / Microsoft Entra access token
                           -> TLS Azure Database for PostgreSQL connection
                           -> owner-approved view only
```

The Azure proof covered this adapter's identity, database, and direct MCP tool
path. HomeLab server-side dry-run proved schema admission for this adapter's
kagent and Agent Gateway manifests. A separate earlier adapter proved the
Gateway/A2A runtime pattern, but this exact three-tool adapter still requires
an end-to-end Gateway/A2A receipt in the work environment.

## Inputs to obtain at work

| Input | Owner/use |
|---|---|
| `WORK_KUBE_CONTEXT` | Approved AKS deployment target |
| `FASTMCP_ENTRA_IMAGE` | Internally built, scanned, signed, digest-pinned image |
| `UAMI_CLIENT_ID` | Kubernetes ServiceAccount annotation |
| `UAMI_OBJECT_ID` | PostgreSQL Entra principal mapping |
| `UAMI_ROLE_NAME` | Unique Entra display name used as the PostgreSQL role |
| `POSTGRES_HOST` | Approved private Flexible Server FQDN |
| `POSTGRES_DATABASE` | Approved database |
| `APPROVED_SCHEMA` / `APPROVED_VIEW_NAME` | SQL-template inputs for the data-owner-approved view |
| `APPROVED_VIEW` | Kubernetes runtime value: `APPROVED_SCHEMA.APPROVED_VIEW_NAME` |
| `DENIED_BASE_TABLE_NAME` | SQL-template input for the negative permission target |
| `DENIED_BASE_TABLE` | Kubernetes verifier value: `APPROVED_SCHEMA.DENIED_BASE_TABLE_NAME` |
| `MODEL_CONFIG` | Existing approved kagent ModelConfig |
| `PRIVATE_RECEIPT_PATH` | Owner-only A2A evidence destination |

`UAMI_CLIENT_ID` and `UAMI_OBJECT_ID` are different identifiers. Confirm both
with the identity owner rather than substituting one for the other.

## 1. Build and publish internally

Build from `adapter/`. Use the approved work CI and registry;
scan and sign the result, then record the immutable digest.

```sh
docker build -t {{INTERNAL_REGISTRY}}/platform/fastmcp-postgres-entra:{{VERSION}} \
  work-agent-bundles/postgres-fastmcp-entra-uami/adapter
docker push {{INTERNAL_REGISTRY}}/platform/fastmcp-postgres-entra:{{VERSION}}
```

Render `FASTMCP_ENTRA_IMAGE` as
`{{INTERNAL_REGISTRY}}/platform/fastmcp-postgres-entra@sha256:{{IMAGE_DIGEST}}`.
Do not deploy a mutable tag.

## 2. Federate the UAMI

The platform identity owner creates an AKS federated identity credential with:

```text
issuer:  the target AKS OIDC issuer
subject: system:serviceaccount:fastmcp-entra-poc:fastmcp-postgres-entra
audience: api://AzureADTokenExchange
```

Do not add an Azure client secret. The Pod label and ServiceAccount annotation
in `aks-workload-identity.yaml.template` activate workload identity.

## 3. Map the UAMI in PostgreSQL

The database team enables Microsoft Entra authentication and runs the two SQL
templates in order:

1. `adapter/01-create-entra-principal.sql.template` in the `postgres` database;
2. `adapter/02-grant-approved-view.sql.template` in `POSTGRES_DATABASE`.

The mapped principal is a regular non-admin role. Grant only `CONNECT`, schema
`USAGE`, and `SELECT` on the approved view. The two final checks in the second
template must return `false`. Do not leave a human bootstrap Entra admin merely
for the application runtime; retain administrators only under the database
team's normal operating policy.

## 4. Render and deploy FastMCP

Create the private values file and render the complete bundle:

```sh
cd work-agent-bundles/postgres-fastmcp-entra-uami
cp work-values.env.template work-values.env
${EDITOR:-vi} work-values.env
kubectl kustomize . > {{PRIVATE_RENDERED_FILE}}
if grep -n '{{' {{PRIVATE_RENDERED_FILE}}; then
  echo 'unresolved placeholders remain' >&2
  exit 1
fi
```

Keep the host, database, identity IDs, registry location, and work object names
outside the public repository. The federated subject must use the rendered
namespace: `system:serviceaccount:FASTMCP_NAMESPACE:fastmcp-postgres-entra`.

Before applying:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_RENDERED_FILE}}
```

Then apply and wait for the digest-pinned Deployment:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_RENDERED_FILE}}
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{FASTMCP_NAMESPACE}} \
  rollout status deployment/fastmcp-postgres-entra --timeout=180s
```

The rendered Deployment must contain no `Secret`, `secretKeyRef`, PostgreSQL
password, connection string, or token. `POSTGRES_HOST` and database/view names
are configuration, not authentication material; keep work coordinates private
according to local policy.

## 5. Run the identity/database gates

Run the marker-only verifier from the Pod before adding an Agent:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{FASTMCP_NAMESPACE}} \
  exec deployment/fastmcp-postgres-entra -- python /app/verify_live.py
```

Pass requires every marker through `FASTMCP_ENTRA_DATABASE_GATES_PASS`.
The verifier prints no token, row data, database identity, or endpoint.

## 6. Add Agent Gateway and kagent

Validate `adapter/agentgateway-kagent.yaml.template` against the installed CRDs, render
`MODEL_CONFIG`, and apply it. The Gateway and Agent allowlists must both equal
the three discovered FastMCP tools exactly. Then run `adapter/verify-live.sh` with an
owner-only receipt path.

If work and HomeLab use different versions, repeat server-side dry-run and live
tool discovery. Do not assume the proven HomeLab CRD schema is portable.

## Acceptance boundary

The lift-and-shift is complete only when:

- the image is internally built, scanned, signed, and digest-pinned;
- the Pod obtains tokens through workload identity with no password Secret;
- the approved view succeeds and base-table/write checks fail closed;
- Gateway and Agent tool lists contain only the three typed tools;
- an A2A receipt proves the Agent called the approved tool; and
- private DNS, private endpoint routing, and TLS are verified in the work
  environment.
