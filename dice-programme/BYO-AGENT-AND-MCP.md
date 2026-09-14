# Bring your own agent and MCP

## Purpose

The Dice bring-your-own-agent workflow gives application and engineering teams a supported way to deploy agents and MCP servers on the shared platform. Teams supply the agent's job and tests. The platform supplies the runtime, model gateway, identity, policy, tool controls, GitOps delivery, and audit records.

This workflow prevents every team from building a separate agent platform. It also prevents a team-owned agent from choosing its own credentials, model endpoint, or cluster-wide tools.

## Team experience

1. The team copies the request template into its GitLab project.
2. The team describes the agent, owner, model class, expected usage, data classification, evaluation cases, and required MCP tools.
3. Dice validates the request and checks each requested tool against the shared MCP catalog.
4. If the request includes a new MCP, Dice deploys it into quarantine, lists its tools, scans the tool names and permissions, and sends exceptions to the platform team.
5. Dice produces an Agent CR, `ToolGrant`, namespace policy, workload identity, resource budget, network policy, and agentgateway route as a merge request.
6. The team and platform owner review the generated change.
7. Flux deploys the merged change.
8. Dice runs allowed-tool, denied-tool, model-route, budget, and A2A smoke tests. The result is posted to the merge request and the service record.

## Ownership

| Team owns | Platform owns |
|---|---|
| Agent purpose and instructions | kagent and Agent CRD support |
| Service owner and support route | agentgateway and approved model routes |
| Evaluation cases and expected answers | MCP catalog and quarantine process |
| Data classification and retention needs | Workload identity and secret delivery |
| Requested tools and business justification | `ToolGrant`, admission policy, and network policy |
| Expected request volume and budget | Usage limits, audit, and platform monitoring |
| Application-specific runbooks | GitOps templates and onboarding workflow |

## Minimum request

Each request must identify:

- the owning team and support contact;
- the agent name, namespace, and business purpose;
- the approved model class rather than a direct provider endpoint;
- the input and output data classifications;
- the expected daily requests, token budget, CPU, and memory;
- each MCP server and exact tool name requested;
- whether each tool reads or writes;
- the target clusters, namespaces, databases, or projects;
- evaluation cases, failure behavior, and timeout behavior;
- the change and incident routes;
- the requested expiry or review date.

## MCP admission

An existing catalog entry can proceed to a `ToolGrant`. A new MCP must pass quarantine first. The admission flow must:

1. deploy the MCP only in the quarantine namespace;
2. discover its tools through the MCP protocol;
3. inspect its image, transport, authentication, and network destinations;
4. classify every tool as read, write, or administrative;
5. reject undeclared or dangerous tools by default;
6. create a versioned `ToolCatalogEntry` after platform approval;
7. grant only the named tools to the named agent;
8. prove that an ungranted tool call fails.

Changing an MCP version starts a new admission. Dice must not replace a verified catalog entry in place.

## Required controls

- All model calls use agentgateway. Teams do not store provider credentials.
- Each agent has a team identity, namespace, resource budget, and cost attribution.
- The platform grants tools by agent, MCP version, and tool name.
- Read and write tools use separate grants and identities.
- A write-capable agent uses the Dice human-approval plugin before execution.
- Network policy permits only DNS, agentgateway, and approved MCP destinations.
- The platform records tool discovery, policy decisions, deployments, and smoke-test results.
- A failed evaluation, deny test, or budget test blocks promotion.
- Revoking a `ToolGrant` or disabling the agentgateway route stops new tool or model use.

## First canary

The first canary should use one non-production namespace and a read-only agent. The agent should use one shared model route and one existing read-only MCP. Add one small team-owned MCP only after the base Agent CR path passes.

The canary is complete when:

- GitLab holds the reviewed request and generated manifests;
- the Agent CR becomes Ready through the shared agentgateway route;
- the allowed MCP tool succeeds;
- an ungranted tool fails;
- the agent cannot reach a model provider directly;
- usage appears under the correct team and cost centre;
- the A2A evaluation returns the expected answer;
- revocation disables access without deleting the audit record.

## Repository starting points

- `infra/byo-kagent/README.md`
- `infra/byo-kagent/SANDBOX-ONBOARDING.md`
- `infra/byo-kagent/crds/`
- `infra/byo-kagent/kyverno-policies/`
- `infra/byo-kagent/bootstrap-catalog/`
- `platform/agentgateway/`
- `work-agent-bundles/gitlab-mcp-gitops-pr/`
- `work-agent-bundles/hitl-remediation-approval/`

These files contain the current design and reusable assets. They do not prove that the complete team onboarding path is live in a work cluster.
