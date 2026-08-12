# Proposed GitLab issue: validate kagent access to governed Starburst data products via MCP

**Suggested title:** Design review: kagent + Starburst data-mesh MCP proof of concept

**Suggested labels:** architecture, data-platform, kubernetes, ai-agent, poc

## Why this issue exists

We have been asked to close a gap: enable an AI agent to retrieve governed
business/operational data through an MCP tool, without giving the agent broad
database credentials or unrestricted write capability.

We do not yet have sufficient visibility of the existing Starburst/data-mesh
endpoint, data products, authentication model, or current tools. This issue is
therefore a design-review and discovery request, not a request to deploy against
production data.

## What has been proven in HomeLab

A bounded, disposable Kubernetes POC passed live:

    kagent Agent
      -> explicit three-tool RemoteMCPServer binding
      -> constrained Streamable HTTP MCP adapter
      -> official Trino SQL engine
      -> synthetic data only

The live verifier confirmed:

- synthetic SQL query succeeded;
- kagent discovered exactly three MCP tools;
- the Agent was Accepted=True, Ready=True; and
- the adapter exposed neither arbitrary SQL nor a write tool.

Evidence and reproducible YAML/scripts:
- [HomeLab POC README]({{REPO_URL}}/work-agent-bundles/starburst-trino-data-mcp-poc/README.md)
- [live proof receipt]({{REPO_URL}}/work-agent-bundles/starburst-trino-data-mcp-poc/evidence/POC-RUN-2026-08-12.md)
- [office replication guide]({{REPO_URL}}/work-agent-bundles/starburst-trino-data-mcp-poc/OFFICE-REPLICATION.md)

## Proposed production-shaped design

~~~mermaid
flowchart LR
  U[Authorised user / workflow] --> A[kagent data agent]
  A -->|Explicit tool allowlist| R[RemoteMCPServer]
  R -->|HTTPS + approved auth| S[Starburst Enterprise native MCP]
  S --> P[Published governed data product]
  P --> V[Curated views / parameterised query templates]
  S --> Q[Query ID + audit history]
  Q --> E[Redacted evidence receipt]

  X[No broad DB credentials in kagent] -.-> A
  W[No write tools] -.-> A
~~~

The preferred endpoint is Starburst Enterprise's native authenticated MCP
endpoint. The HomeLab Trino adapter is an integration rehearsal only; it is
not proposed as the work production solution if native Starburst MCP is
available.

For a first office POC, mount only the discovered equivalents of:

    searchDataProducts
    getDataProductDetails
    listParametrizedQueryTools
    parametrizedQuery

Use parameterised queries first. They let the data team own the SQL, tables,
typed input, and constraints. Do not expose general queryReadOnly until it
has explicit data-owner approval.

## Comparison: current known state vs proposed POC

| Area | Current known state | Proposed POC | Decision needed |
|---|---|---|---|
| kagent/MCP integration | HomeLab integration proven | Same kagent tool-binding pattern | Is kagent available in a non-production namespace? |
| Data engine | Starburst/data mesh reported; details unknown | Starburst native MCP, not a custom driver adapter | Is native MCP enabled/licensed on the target environment? |
| Data contract | Unknown | One synthetic or masked published data product | Which product/views and business question are suitable? |
| Authentication | Unknown | Dedicated non-human read-only identity | Which supported auth flow should the MCP client use? |
| Query control | Unknown | Parameterised queries, limits, no writes | Are parameterised query tools/data products available? |
| Audit | Unknown | Query ID, actor, tool call, redacted result receipt | What query history/audit evidence can be retrieved? |
| Images/air-gap | Unknown | Internal registry and pinned approved images/charts | What registry and supply-chain process applies? |
| Agent Gateway | Not proven in the HomeLab data path | Optional policy/telemetry layer after version validation | Is it required or useful for this route? |

## Questions for the Starburst/data/platform teams

### Starburst and data-mesh

1. Are we using Starburst Enterprise, Starburst Galaxy, or another
   Trino-compatible endpoint? Which version?
2. Is Starburst's native MCP server available and licensed in a non-production
   environment?
3. Can we have one HTTPS /mcp endpoint for a non-production POC?
4. Which authentication methods are supported for a non-human Kubernetes
   workload? Is workload identity/token exchange available?
5. Is there a published synthetic or masked data product we can use?
6. Can that product expose a small parameterised query set and metadata for
   discovery?
7. What role grants are required for only that product/views?
8. What result-size, execution-time, resource, and cost guardrails can be set?
9. What query ID and audit/query-history evidence can the POC collect?
10. Can we prove denial for an out-of-scope product without touching production
    data?

### Kubernetes/platform

1. Which non-production cluster/namespace is approved?
2. Is kagent already installed and connected to an approved model route?
3. What is the approved path for secretless workload identity or short-lived
   tokens?
4. Is Agent Gateway required for MCP traffic, and does the installed release
   support the intended authentication/policy controls?
5. Which internal registry and Helm/OCI repositories must be used?
6. What NetworkPolicy, TLS/CA, proxy, egress, scanning, signing, and logging
   controls apply?

## Proposed acceptance criteria

- [ ] Native Starburst MCP availability/licensing is confirmed, or a documented
  fallback decision is made.
- [ ] A non-production HTTPS endpoint, synthetic/masked data product, and
  read-only non-human identity are approved.
- [ ] The RemoteMCPServer is Accepted=True, and its discovered tools match
  the Agent's explicit allowlist.
- [ ] The Agent is Accepted=True, Ready=True.
- [ ] One discover -> metadata -> parameterised query journey produces the
  expected redacted result.
- [ ] A Starburst query ID and audit/query-history receipt are attached.
- [ ] An out-of-scope data product is denied.
- [ ] No write or general database credentials are mounted in the Agent.
- [ ] All images/charts are supplied from approved internal sources.
- [ ] POC resources and temporary identity are removed or handed to a named
  owner.

## Requested outcome

Please review the model and answer the questions above. At the end of this
issue, we should jointly decide one of:

1. **Proceed with native Starburst MCP POC** — preferred.
2. **Run a temporary Trino integration rehearsal** — only if native Starburst
   MCP is not yet available; not a production-equivalence claim.
3. **Stop/rework** — if the identity, governance, licensing, or audit boundary
   cannot meet the acceptance criteria.

No production deployment, real-data access, write operations, credential
sharing, or external publication is authorised by this issue.
