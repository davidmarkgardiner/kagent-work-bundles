# PostgreSQL MCP workplace POC — start here

The primary workplace path is one FastMCP implementation with two separate
authentication deployments. Do not deploy the MCPg bundle for this proof.

For the comparison with retrieval-assisted text-to-SQL and the recommended
shared-backend integration, read
[`postgres-natural-language-query-integration/`](postgres-natural-language-query-integration/).

## Path A — deploy first: FastMCP username/password

Use
[`postgres-fastmcp-entra-uami/password/`](postgres-fastmcp-entra-uami/password/)
with the existing PostgreSQL username/password. This runs the same FastMCP
image, tools, and approved-view queries as the later UAMI deployment.

1. Build, scan, sign, and push the shared adapter image.
2. Create the username/password Secret through the approved secret-delivery
   path; never put either value in Git or `work-values.env`.
3. Copy `password/work-values.env.template` to the ignored `work-values.env`
   and replace every placeholder.
4. Render and check it: `kubectl kustomize
   work-agent-bundles/postgres-fastmcp-entra-uami/password`.
5. Run server-side dry-run, then deploy the same Kustomize target.
6. Run the shared database, Gateway discovery, and A2A verification gates.

## Path B — strategic target: FastMCP with UAMI

Use the root [`postgres-fastmcp-entra-uami/`](postgres-fastmcp-entra-uami/)
Kustomize target when the
identity/database teams provide the UAMI client ID, service-principal object ID,
unique Entra role name, federated identity credential, and PostgreSQL role
mapping.

1. Reuse the same digest-pinned adapter image proven by Path A.
2. Copy `work-values.env.template` to the ignored `work-values.env` and replace
   every placeholder with values verified from the current environment.
3. Have the database team render/run the two SQL templates with the matching
   object ID, role, database, schema, view, and negative-test table.
4. Render: `kubectl kustomize work-agent-bundles/postgres-fastmcp-entra-uami`.
5. Confirm no `{{PLACEHOLDER}}` remains, then run server-side dry-run and deploy
   with `kubectl apply --dry-run=server -k ...` and `kubectl apply -k ...`.
6. Run the marker-only database verifier, Gateway discovery, and A2A receipt
   checks from the FastMCP README.

Moving from Path A to Path B changes only the FastMCP Pod's database
authentication wiring. The MCP tools, queries, Service, Gateway route,
RemoteMCPServer, and Agent stay the same. Prove Path B through the same
acceptance gates before removing the password Secret.

## Separate legacy/reference path: MCPg

[`postgres-mcpg-password/`](postgres-mcpg-password/) remains available as a
separate MCPg v0.7.1 reference bundle. It is not one of the two FastMCP
authentication modes and is not required for this installation.
