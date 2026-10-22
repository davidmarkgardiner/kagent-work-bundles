# Design evidence

Inspected 21 October 2026. No target cluster was contacted for this design. These are source observations, not deployed-policy results.

| Source | Observation |
| --- | --- |
| [ToolGrant schema](../../../infra/byo-kagent/crds/toolgrant-crd.yaml) | Existing namespace-scoped `platform.kagent.dev/v1alpha1` request names an Agent, catalog version, tools and optional expiry. It has no runtime enforcement mechanism. |
| [Catalog schema](../../../infra/byo-kagent/crds/toolcatalogentry-crd.yaml) | Existing cluster-scoped catalog contains source metadata and verified tool classifications. It does not pin all adapter behavior, downstream resource scope or input schemas. |
| [Grant admission policy](../../../infra/byo-kagent/kyverno-policies/validate-agent-tool-grants.yaml) | Lines 50-60 check only whether any grant names the Agent. The rule called `verify-toolgrant-not-expired` repeats that count at lines 78-95. Neither rule matches individual tool/catalog approvals or compares expiry. |
| [Catalog status policy](../../../infra/byo-kagent/kyverno-policies/protect-catalog-status.yaml) | Restricts status writer and freezes `verifiedAt`. A timestamp does not bind the complete executable and authorization contract. |
| [HostedAgent contract](../../../platform/skills-registry/hosted/contract.py) | Lines 49-50 reject nonempty `toolGrantRefs`. Generated declarative tools are empty. The current immutable documentation profile remains unchanged. |
| [Gateway ownership design](../../../platform/agentgateway/APPLICATION-TEAM-ONBOARDING-PLAN.md) | Lines 282-301 identify the per-Agent workload identity and authenticated A2A prerequisites. Shared identity or unsigned attribution headers do not establish per-Agent authorization. |
| [Application front sheet](../../../platform/agentgateway/APPLICATION-TEAM-ONBOARDING-FRONT-SHEET.md) | Keeps shared gateway routes, policies, backends and credentials outside team control. |

The local upstream KAgent checkout was at `9fd3c84dc01f9f29a5257af883537a56af9ea274`; the local agentgateway checkout was at `4ae9c329a28baa994f55a29a93989903bfd6bb3b`. Their checked-out versions are not assumed to match a target deployment.

The exact KAgent `v0.7.13` tag contains `RemoteMCPServer.headersFrom`, explicit Agent `toolNames`, `allowedHeaders`, and an optional STS plugin. Those API/code paths alone do not prove per-Agent token minting, renewal, authenticated session ownership or gateway audience behavior in the lab. No shared static authorization credential is proposed as a substitute.

The current official [Kubernetes tool-access guide](https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/tool-access/) documents tool authorization using validated JWT claims. The [authorization guide](https://agentgateway.dev/docs/kubernetes/latest/documentation/security/authorization/) requires JWT authentication to supply those claims. These support the gateway layer in the proposed design and do not validate an installed version.

The current [MCP authorization reference](https://agentgateway.dev/docs/standalone/latest/documentation/configuration/security/mcp-authz/) distinguishes tool names and target names from argument availability. It states that `mcp.tool.arguments` is unavailable to `mcpAuthorization`, while describing route-level argument handling separately. This design makes downstream resource restriction an adapter/RBAC responsibility and does not depend on a particular gateway argument-policy implementation.

The official [MCP tool-annotation explanation](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/) treats `readOnlyHint` as a hint. This design requires reviewed typed operations and downstream grants rather than trusting that annotation.

Review availability. The architecture comparison uses one native Codex candidate and the parent's independent alternative. The earlier Claude usage limit was still active; Grok CLI was absent on a fresh executable lookup. Neither supplied a review. A native judge supplies an independent check, with the reduced provider diversity stated in the decision record.
