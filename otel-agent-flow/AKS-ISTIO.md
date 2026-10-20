# Serve the demo through the AKS Istio add-on

Use the existing managed Istio ingress gateway. Set `ingress.istio.existingGateway` to the approved Gateway reference as `namespace/name`. The chart then creates only `VirtualService/flow-demo` in the demo namespace. Leave the reference empty to create a dedicated `Gateway/flow-demo` in `aks-istio-ingress`. It does not install Istio or modify the managed gateway Deployment.

The default selector is `istio: aks-istio-ingressgateway-internal`. Set `ingress.istio.selector` to the verified external selector only when the approved work exposure requires it. The TLS Secret named by `ingress.tlsSecret` must exist in `aks-istio-ingress`, where the gateway proxy reads it. The approved Key Vault/certificate integration owns its private key and renewal.

The chart-owned Gateway redirects HTTP to HTTPS and terminates TLS in SIMPLE mode on port 443. An existing Gateway must already provide the approved HTTPS listener and redirect. The VirtualService exposes exact UI/API paths and forwards them to `flow-dashboard` on port 8787. `/v1/traces`, `/v1/logs`, the model gateway, MCP server, and collector receiver ports have no ingress route.

This integration follows Microsoft's managed gateway selector and TLS Secret contract:

- https://learn.microsoft.com/en-us/azure/aks/istio-secure-gateway
- https://learn.microsoft.com/en-us/azure/aks/istio-deploy-ingress

## Target-cluster checks

Use the work team's normal DNS, certificate, authentication, and private/public load-balancer policy. The chart does not create Azure resources, DNS records, Key Vault identities, or an SSO deployment.

Check the installed add-on revision and its compatibility with the actual AKS version. Check that the selected ingress pods carry the selector in the operator values. Check the TLS Secret in the gateway namespace and ensure the certificate SAN covers the configured hostname. Run `istioctl analyze` with the target's supported tooling after rendering/applying the manifests. Confirm HTTP redirect, certificate trust, the approved audience/access policy, and blocked OTLP paths through the real load balancer.

The current profile is ingress-only. Application pods explicitly disable sidecar injection. Substrate has its own actor identity, mTLS, egress interception, and sandbox networking. Do not enable namespace-wide injection on its worker pool merely to match the presence of the AKS add-on. If work policy mandates sidecars, stop at the compatibility gate and test that architecture separately.

The local HTTPS proxy verifies the application contract and the verifier's TLS/path behavior. It does not prove managed Istio reconciliation, Azure load balancing, Key Vault synchronization, DNS, mesh mTLS, or CNI enforcement. Capture those checks on AKS before calling the work deployment accepted.
