# AKS Entra overlay

Apply this profile only after replacing every `{{PLACEHOLDER}}` and installing Gateway API v1.6.2 experimental CRDs. The official v1.5 guide used v1.6.0 experimental; this bundle pins the latest v1.6 patch available at build time and requires server-side dry-run before promotion.

For each team, create a public-client Entra app registration for interactive MCP access, expose an API scope, and create a team-specific app role. Keep the A2A app role and MCP app role distinct. Use the v2 issuer only when the tokens actually contain that `iss`. The policy accepts both documented Entra audience forms.

`entra-jwks.yaml` belongs in `tenant-gateway-system`. Each team MCP policy replaces the red MCP JWT policy. The three A2A policy files replace the red A2A JWT policies with strict Entra audience and app-role checks. The Substrate specialist gets a separate `platform-substrate.a2a.invoke` role. `mcp-route-patches.yaml` replaces the two red MCP HTTPRoutes with the three documented MCP and discovery path matches plus the browser CORS filter.

Render or substitute the placeholders, then validate in this order:

```sh
kubectl apply --server-side --dry-run=server -f entra-jwks.yaml
kubectl apply --server-side --dry-run=server -f event-mcp-policy.yaml
kubectl apply --server-side --dry-run=server -f chat-mcp-policy.yaml
kubectl apply --server-side --dry-run=server -f event-a2a-policy.yaml
kubectl apply --server-side --dry-run=server -f chat-a2a-policy.yaml
kubectl apply --server-side --dry-run=server -f substrate-a2a-policy.yaml
kubectl apply --server-side --dry-run=server -f mcp-route-patches.yaml
```

Kagent runtime calls do not use browser PKCE. Supply a short-lived application token for the team's MCP audience through an approved workload identity token broker or native runtime support. Prove refresh across expiry before calling the AKS profile production-ready.

This overlay does not choose an AKS ingress controller, public IP, DNS zone, certificate issuer, or secret store. Add HTTPS listeners with organization-owned hostnames and certificate references, then prove external TLS before promotion. The in-cluster red Gateway is intentionally HTTP-only.

Source: https://agentgateway.dev/docs/kubernetes/latest/documentation/mcp/auth/entra/
