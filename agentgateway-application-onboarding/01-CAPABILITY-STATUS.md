# Agentgateway capability and evidence status

Snapshot basis: repository branch `docs/agentgateway-app-team-onboarding`,
agentgateway manifest baseline v1.3.1. Recheck the installed target before the
meeting; repository state is not live-cluster state.

## Status definitions

| Status | Meaning |
|---|---|
| Configured | Checked-in manifest or documented contract exists |
| Lab-verified | A named lab/version has behavioural evidence |
| Target proof required | Must be revalidated against work CRDs, identity and network state |
| Proposed | Design or example exists but no deployable/runtime-proven control is established |
| Blocked | Known installed-schema or security condition prevents use |

## Capability matrix

| Capability | Repository evidence | Status for customer demonstration | Boundary/caveat |
|---|---|---|---|
| Gateway API front door | `GatewayClass`, `Gateway` and model `HTTPRoute` objects in `platform/agentgateway/gateway-resources.yaml` | Configured; target proof required | Listener permits routes from all namespaces; admission and ownership controls must constrain who can create them |
| OpenAI-compatible model route | `/openai/v1` and `/azure/v1` routes plus backend examples | Lab-verified on agentgateway v1.1.0; v1.3.1 target proof required | Model Garden endpoint/provider contract is still a Phase 0 input |
| Gateway-to-model identity | Azure UAMI and custom-scope token examples | Configured; target proof required | Model Garden team must confirm endpoint, audience/scope and authorize the backend identity |
| Caller JWT authentication | Strict `AgentgatewayPolicy` example | Proposed for target onboarding | `oidc-proxy` is illustrative and absent; JWKS egress, DNS, CA trust, caching and rollover need owners/evidence |
| Caller API key | Documented strict API-key alternative | Available only as a temporary exception | Weaker attribution/rotation; not the production default |
| Claim/route authorization | Design uses validated JWT claims and route-specific policy | Proposed; target proof required | Authentication alone does not authorize models, MCPs or resources |
| Prompt guard | PII reject/mask examples for model routes | Configured; target proof required | Pattern coverage is intentionally narrow and must match approved data policy |
| Rate limiting | Local per-route examples | Configured; target proof required | Per data-plane replica, not a fixed cost-centre budget |
| Timeouts | Model and A2A request timeout examples | Configured; target proof required | Client, ingress, gateway and backend timeout ordering must be tested together |
| Model failover | Priority/retry example under `/llm/v1` | Configured optional example; not current POC scope | Gateway-generated 429 is not provider failover; installed health-policy fields were previously absent |
| MCP routing | Static/selector MCP backend and `HTTPRoute` examples | Configured pattern; target proof required | Direct MCP Service access must be blocked |
| MCP tool filtering | CEL `mcp.tool.name` allowlist examples | Configured pattern; PostgreSQL tools lab-verified | Tool name does not constrain database, namespace, cluster or subscription by itself |
| PostgreSQL schema MCP | MCPg v0.7.1 bundle with three schema tools | Lab-verified candidate for first POC | Work overlay, database identity and installed CRDs still need target proof |
| GitLab MCP | GitOps-PR proof bundle and checklist | Candidate, not platform-approved | Official server/approved wrapper, project scope and tool discovery remain TODO |
| Kubernetes MCP | Research and separate bounded bundles | Candidate, not platform-approved | Never place a fleet-wide credential behind a tenant route; require scoped identity/context evidence |
| Argo OpenAPI MCP | Checked-in backend/route/policy example | Blocked | Inspected CRD did not support `targets[].openapi`; manifests say do not apply |
| A2A routing | HTTPRoute, rewrite, rate-limit and timeout; proxmox data-path receipt | Lab-verified routing only | Gateway policy has no A2A identity check on inspected release; not tenant-isolated until Phase 3 evidence |
| MCP/A2A catalogue grants | `ToolCatalogEntry`/`ToolGrant` CRDs and examples | Proposed platform control | Checked-in proposal artifacts are not a proven renderer/runtime control |
| Metrics and alerts | PodMonitor, ServiceMonitor and PrometheusRule examples | Token metrics lab-verified on v1.1.0; target proof required | Confirm actual port/labels and prompt/token redaction on v1.3.1 |
| Network containment | NetworkPolicy and Istio examples | Configured with known review gaps | Validate actual CNI/mesh source identity, egress CIDRs and true default-deny behaviour |
| Secret rotation | Gateway backend SecretRef rotation receipt | Lab-verified on v1.1.0 | Prefer Workload Identity for Model Garden; revalidate rotation path after upgrade |

## Safe claims in the meeting

- Agentgateway can be the common governed route to model and MCP backends.
- The repository contains working patterns and selected lab evidence.
- The onboarding contract deliberately requires live allow and deny evidence
  before a capability is advertised to an application team.

## Claims not yet justified

- “Strict JWT is already live for every application.”
- “PostgreSQL, GitLab and Kubernetes MCP are all approved catalogue services.”
- “A2A is tenant-authenticated by agentgateway.”
- “Local rate limits are billing limits.”
- “Ready/Accepted status proves authorization and containment.”
