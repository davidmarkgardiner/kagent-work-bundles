# Evidence policy

Retain only sanitized receipts:

- source commit and immutable image digest;
- Helm lint/template results;
- reader positive and negative RBAC summary;
- generated context aliases and count, never server URLs or auth information;
- immutable Secret name, never Secret data;
- pod readiness, resolved image ID and mounted Secret name;
- direct and gateway discovered tool names;
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
