# PostgreSQL inventory data-contract skill

This is a deployable kagent skill-image example for the MCPg read-query Agent.
It gives the Agent the approved data contract, query procedure, and response
format without giving it more MCP tools or PostgreSQL permissions.

## What it does

```text
skill image -> kagent SkillsTool -> data-contract guidance
                                      +
MCPg run_select -> Agent Gateway allowlist -> SELECT-only database role
```

The skill is useful for domain meaning and consistent query selection. It is
not a security boundary. Keep the existing Agent tool allowlist, Agent Gateway
policy, NetworkPolicy, TLS, and database grants in place.

## Make the private work version

1. Replace the illustrative views, columns, classifications, and query
   catalogue beneath `skill/references/` with the data-owner-approved contract.
   Do not add credentials, private endpoints, production rows, tenant IDs, or
   personal data.
2. Build and push the same image to the approved internal registry:

   ```sh
   docker build -t {{INTERNAL_REGISTRY}}/platform/postgres-inventory-data-contract:{{VERSION}} .
   docker push {{INTERNAL_REGISTRY}}/platform/postgres-inventory-data-contract:{{VERSION}}
   ```

3. Resolve the pushed image to an immutable digest and privately render
   `read-query-agent-with-skill.yaml` with:

   ```text
   KAGENT_NAMESPACE
   KAGENT_MODEL_CONFIG
   POSTGRES_INVENTORY_SKILL_IMAGE={{INTERNAL_REGISTRY}}/platform/postgres-inventory-data-contract@sha256:{{SKILL_IMAGE_DIGEST}}
   ```

4. First deploy the parent schema-only bundle and its optional
   [read-query profile](../mcpg-read-query-profile/). Then apply this rendered
   Agent as the replacement for `postgres-inventory-read-query-agent`.
5. Confirm the Agent becomes `Accepted=True` and `Ready=True`, inspect its Pod
   for successful skill-image initialisation, then use the outside-in checklist
   to prove one approved namespace-count question.

The image must be reachable by the cluster's kubelet. Use the existing
workload identity/ACR or approved image-pull mechanism; a skill image does not
need database credentials.

## What is deliberately not in this example

- a complete work schema or actual view names;
- a database username, password, endpoint, certificate, or connection string;
- broader MCPg tools, writes, or generic unrestricted SQL; or
- a claim that MCPg can authenticate to Azure PostgreSQL with AKS workload
  identity.

See [WORKLOAD-IDENTITY-DECISION.md](WORKLOAD-IDENTITY-DECISION.md) for the
MCPg boundary and the FastMCP recommendation for an Entra/UAMI database path.
