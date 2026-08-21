# FastMCP PostgreSQL password-to-UAMI work bundle

This bundle contains one bounded FastMCP implementation and two PostgreSQL
authentication deployments:

1. [`password/`](password/) for the existing username/password connection;
2. the root Kustomize target for the later AKS Workload Identity/UAMI path.

Deploy the password path first. When the database team supplies the UAMI and
PostgreSQL Entra mapping, deploy the root UAMI target using the same image. The
three tool names, parameters, approved-view SQL, Service, Gateway route,
RemoteMCPServer, Agent, and verification flow remain the same.

This is a self-contained work bundle. Its deployable source is
[`adapter/`](adapter/), and its live sanitized proof is
[`evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md`](evidence/FASTMCP-ENTRA-AKS-UAMI-POC-2026-08-19.md).
MCPg is not part of this workflow. Do not mix this bundle with the separate
MCPg examples at `../postgres-mcpg-password/`.

Run `scripts/verify-bundle.sh` before handoff. It renders both authentication
paths, checks that their identity wiring remains separate, validates the shared
adapter source, and runs the public-safety scan.

For workplace rendering, copy `work-values.env.template` to the ignored
`work-values.env`, replace every placeholder with values checked against the
current environment, and use this directory as the Kustomize target. The
same values file carries the database-team SQL inputs so the client ID, object
ID, role, schema, view, and denial-test table can be cross-checked in one place.
The rendered ConfigMap contains coordinates and IDs but no credential or token.

## Shared architecture

```text
kagent -> Agent Gateway -> FastMCP Service
                           -> password Secret today
                              or
                           -> AKS Workload Identity/UAMI later
                           -> TLS PostgreSQL connection
                           -> owner-approved view only
```

`POSTGRES_AUTH_MODE=password` uses Secret-backed `POSTGRES_USER` and
`POSTGRES_PASSWORD`. `POSTGRES_AUTH_MODE=entra` uses
`DefaultAzureCredential` and a fresh Entra-authenticated connection. Neither
mode changes the MCP tool contract or query functions.

The Azure proof covered the UAMI adapter's identity, database, and direct MCP
tool path. HomeLab server-side dry-run proved schema admission for this adapter's
kagent and Agent Gateway manifests. A separate earlier adapter proved the
Gateway/A2A runtime pattern, but this exact three-tool adapter still requires
an end-to-end Gateway/A2A receipt in the work environment.

## Deploy first: username/password FastMCP

Build the shared adapter image once, then create a private Secret through the
approved work secret-delivery mechanism. The Secret must contain the existing
PostgreSQL username and password under the keys configured in
`password/work-values.env`; do not put either value in Git, a ConfigMap, the
values file, or terminal evidence.

```sh
cd work-agent-bundles/postgres-fastmcp-entra-uami/password
cp work-values.env.template work-values.env
${EDITOR:-vi} work-values.env
kubectl kustomize . > {{PRIVATE_PASSWORD_RENDERED_FILE}}
if grep -n '{{' {{PRIVATE_PASSWORD_RENDERED_FILE}}; then
  echo 'unresolved placeholders remain' >&2
  exit 1
fi
kubectl --context {{WORK_KUBE_CONTEXT}} apply --dry-run=server \
  -f {{PRIVATE_PASSWORD_RENDERED_FILE}}
kubectl --context {{WORK_KUBE_CONTEXT}} apply \
  -f {{PRIVATE_PASSWORD_RENDERED_FILE}}
```

The password Deployment disables ServiceAccount token automounting and obtains
only the two database values through `secretKeyRef`. Run the database and A2A
gates below before calling this path working.

## Later: swap authentication to UAMI

Do not change the tools or rebuild different query logic. Reuse the same
digest-pinned image, complete the identity/database inputs below, render the
root Kustomize target, and apply it over the password Deployment. The root
target replaces the Pod template with the workload-identity ServiceAccount and
removes the username/password Secret references.

Before removing the password Secret, prove token acquisition, approved-view
access, base-table/write denial, a fresh second connection, Gateway discovery,
and the same A2A question through the UAMI Pod.

## UAMI inputs to obtain at work

| Input | Owner/use |
|---|---|
| `WORK_KUBE_CONTEXT` | Approved AKS deployment target |
| `FASTMCP_IMAGE` | Same internally built, scanned, signed, digest-pinned image used by the password proof |
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

## Build and publish the shared image internally

Build once from `adapter/`. Use the approved work CI and registry;
scan and sign the result, then record the immutable digest.

```sh
docker build -t {{INTERNAL_REGISTRY}}/platform/fastmcp-postgres:{{VERSION}} \
  work-agent-bundles/postgres-fastmcp-entra-uami/adapter
docker push {{INTERNAL_REGISTRY}}/platform/fastmcp-postgres:{{VERSION}}
```

Render `FASTMCP_IMAGE` as
`{{INTERNAL_REGISTRY}}/platform/fastmcp-postgres@sha256:{{IMAGE_DIGEST}}`.
Do not deploy a mutable tag.

## UAMI step 1: federate the UAMI

The platform identity owner creates an AKS federated identity credential with:

```text
issuer:  the target AKS OIDC issuer
subject: system:serviceaccount:fastmcp-entra-poc:fastmcp-postgres-entra
audience: api://AzureADTokenExchange
```

Do not add an Azure client secret. The Pod label and ServiceAccount annotation
in `aks-workload-identity.yaml.template` activate workload identity.

## UAMI step 2: map the UAMI in PostgreSQL

The database team enables Microsoft Entra authentication and runs the two SQL
templates in order:

1. `adapter/01-create-entra-principal.sql.template` in the `postgres` database;
2. `adapter/02-grant-approved-view.sql.template` in `POSTGRES_DATABASE`.

The mapped principal is a regular non-admin role. Grant only `CONNECT`, schema
`USAGE`, and `SELECT` on the approved view. The two final checks in the second
template must return `false`. Do not leave a human bootstrap Entra admin merely
for the application runtime; retain administrators only under the database
team's normal operating policy.

## UAMI step 3: render and deploy FastMCP

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

## UAMI step 4: run the identity/database gates

Run the marker-only verifier from the Pod before adding an Agent:

```sh
kubectl --context {{WORK_KUBE_CONTEXT}} -n {{FASTMCP_NAMESPACE}} \
  exec deployment/fastmcp-postgres-entra -- python /app/verify_live.py
```

Pass requires every marker through `FASTMCP_DATABASE_GATES_PASS`. In UAMI mode
it also prints `ENTRA_TOKEN_ACQUISITION_OK`. The verifier prints no token,
password, row data, database identity, or endpoint.

## UAMI step 5: add Agent Gateway and kagent

Validate `adapter/agentgateway-kagent.yaml.template` against the installed CRDs, render
`MODEL_CONFIG`, and apply it. The Gateway and Agent allowlists must both equal
the three discovered FastMCP tools exactly. Then run `adapter/verify-live.sh` with an
owner-only receipt path.

If work and HomeLab use different versions, repeat server-side dry-run and live
tool discovery. Do not assume the proven HomeLab CRD schema is portable.

## Acceptance boundary

The password proof is complete only when the same image, three tools, approved
view, denial checks, Gateway discovery, and A2A receipt pass with
`POSTGRES_AUTH_MODE=password`.

The later UAMI swap is complete only when:

- the image is internally built, scanned, signed, and digest-pinned;
- the Pod obtains tokens through workload identity with no password Secret;
- the approved view succeeds and base-table/write checks fail closed;
- Gateway and Agent tool lists contain only the three typed tools;
- an A2A receipt proves the Agent called the approved tool; and
- private DNS, private endpoint routing, and TLS are verified in the work
  environment.
