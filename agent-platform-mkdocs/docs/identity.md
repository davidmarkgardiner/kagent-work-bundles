# Entra identity and request ownership

Entra Workload Identity/UAMI, Microsoft Entra Agent ID and Substrate Actor identity solve different parts of the request. They are not interchangeable and one successful login does not authorise every hop.

## Two separately owned requests

1. **Caller to Agent:** a human/workload obtains a token for the A2A API. The entry point validates token issuer, audience and validity, then applies the intended caller/role/agent policy.
2. **Agent to downstream model/MCP/API:** the runtime/broker obtains a token for that destination and identity. The destination checks permission and scope. The backend's credential controls its final resource access.

The AKS ServiceAccount's federation subject must be owned and exact. The identity/security owner approves blueprint, child identity, API roles, grants and revocation. Azure RBAC on a managed identity does not imply Microsoft Graph authority to provision Agent IDs.

## App-only versus delegated

App-only access performs background work under the agent/workload's own grants. Delegated/OBO access uses an authorised user's permissions and a token exchanged for the downstream audience. Do not forward an A2A token to an MCP or model API with a different audience. A native Substrate Actor JWT identifies an Actor; Entra will not automatically accept it as an Agent ID token.

Current Microsoft documentation describes both multi-instance blueprints impersonating child identities and single-instance identities. Choose the tenant-approved mode and acquisition library; do not silently transplant an older two-hop example. Feature/API availability, consent and applicable Conditional Access need receiving-tenant review. See [agent identity overview](https://learn.microsoft.com/en-us/entra/agent-id/agent-identities), [app-only](https://learn.microsoft.com/en-us/entra/agent-id/agent-autonomous-app-oauth-flow), [OBO](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow), and [Conditional Access patterns](https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id).

## Authorisation details that must survive migration

Earlier AKS identity testing found that a token with the expected role but the wrong child identity could pass an overly permissive policy. Require the role **and** approved subject in one conjunctive authorisation condition where the policy's separate Allow entries have OR semantics. Inspect actual token claims and the installed gateway schema; never assume a role alone identifies one agent.

That dated receipt used classic kagent, a deterministic model, temporary Secret-based token handoff and broad discovery egress. It did not prove automatic renewal, expiry failure or workplace production identity. kagent 1.0.1 includes an outbound MCP session-identity fix, making identity propagation a specific regression to test.

## Acceptance

Capture issuer/audience and pseudonymised subject/role metadata without token contents. Test wrong identity with the right role, right identity without role, missing/invalid/expired/wrong-audience token, cross-agent credential use, refresh, expiry, disable and revocation. Check destination receipts and backend counters. Explain existing-token validity windows after revocation instead of promising instantaneous invalidation.

Keep populated IDs, tenant/issuer URLs, federation subjects, grants and receipts in private systems. Public configuration uses `{{PLACEHOLDER}}` values. The identity request is a dependency for the work agent, not permission to self-grant.
