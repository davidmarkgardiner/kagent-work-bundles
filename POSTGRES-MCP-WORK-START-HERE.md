# PostgreSQL MCP workplace POC — start here

There are two separate deployment paths. Do not merge their authentication
configuration.

## Path A — available today: MCPg username/password

Use [`postgres-mcpg-password/`](postgres-mcpg-password/) when the database team
provides the existing TLS PostgreSQL connection string. The connection string
is delivered through the approved Secret system as the `postgres-url` key; it
never belongs in Git, an Agent manifest, or terminal evidence.

1. Copy `postgres-mcpg-password/work-values.env.template` to the ignored
   `work-values.env`, fill it with current cluster/registry coordinates, and
   cross-check [`MCPG-WORK-VARIABLES.md`](postgres-mcpg-password/MCPG-WORK-VARIABLES.md).
2. Create the `postgres-url` Secret through the approved secret-delivery path.
3. Render and check it: `kubectl kustomize
   work-agent-bundles/postgres-mcpg-password`.
4. Run server-side dry-run, then deploy the same Kustomize target.
5. Follow the outside-in validation checklist.

## Path B — strategic target: FastMCP with UAMI

Use [`postgres-fastmcp-entra-uami/`](postgres-fastmcp-entra-uami/) when the
identity/database teams provide the UAMI client ID, service-principal object ID,
unique Entra role name, federated identity credential, and PostgreSQL role
mapping.

1. Build, scan, sign, and push the adapter image to the work registry.
2. Copy `work-values.env.template` to the ignored `work-values.env` and replace
   every placeholder with values verified from the current environment.
3. Have the database team render/run the two SQL templates with the matching
   object ID, role, database, schema, view, and negative-test table.
4. Render: `kubectl kustomize work-agent-bundles/postgres-fastmcp-entra-uami`.
5. Confirm no `{{PLACEHOLDER}}` remains, then run server-side dry-run and deploy
   with `kubectl apply --dry-run=server -k ...` and `kubectl apply -k ...`.
6. Run the marker-only database verifier, Gateway discovery, and A2A receipt
   checks from the FastMCP README.

Moving from Path A to Path B changes the MCP implementation and Kubernetes
backend. It is not an in-place credential change to MCPg. Prove Path B through
its own Gateway route and acceptance gates before removing Path A.
