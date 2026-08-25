# Evidence policy

Retain only sanitized receipts:

- source commit and immutable image digest;
- Helm lint/template results;
- reader positive and negative RBAC summary;
- generated context aliases and count, never server URLs or auth information;
- Secret name and content hash, never Secret data;
- pod readiness, resolved image ID and mounted Secret name;
- direct endpoint and gateway-discovered tool names;
- per-context node-count fingerprints;
- 20-request crossover summary;
- kagent Agent Accepted/Ready conditions and a redacted A2A response; and
- teardown or rollback receipt.

Never retain kubeconfigs, bearer tokens, client certificates, private API
addresses, Secret YAML, Authorization headers or raw verbose MCP logs.

Run the repository's bundle verifier and an approved secret scanner against
any additional evidence directory before sharing it.

The sanitized live receipt is
[live-homelab-2026-08-24.md](live-homelab-2026-08-24.md).
The derived image packaging and live MCP compatibility proof is
[derived-image-live-homelab-2026-08-25.md](derived-image-live-homelab-2026-08-25.md).
The Kubernetes-native AKS render and current acceptance boundary are in
[aks-credential-job-render-2026-08-24.md](aks-credential-job-render-2026-08-24.md).
