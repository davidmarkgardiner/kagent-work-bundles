# Linked-guidance local verification

Date: 2026-10-01. Scope: local Python and Docker Desktop; synthetic Cert Manager
catalog. This is not live Proxmox, workplace, or conversational Agent proof.
This records the initial offline phase; the subsequent
[live receipt](LIVE-VERIFICATION-2026-10-01.md) supersedes its pending runtime gates.

| Gate | Observation |
|---|---|
| Proxmox access | Host reachable by existing SSH alias; control-plane and two Kubernetes worker VMs were stopped. Saved Kubernetes API endpoint was unreachable. No VM was started or other worker stopped. |
| Store tests | Nine tests passed: exact identity/scope, rejection of transient Pod/ReplicaSet identities, no prefix match, stale/future review handling, reference/content limits, escaped envelope limit, path/URL rejection, missing-reference startup failure, provenance/synthetic-history marker. |
| HTTP MCP | Official Python MCP SDK 1.30.0 negotiated Streamable HTTP and exposed exactly `find_guidance` and `read_guidance`, both annotated read-only. |
| Direct lookup | Exact lab Deployment binding returned four references. Each current reference could be read; unbound workload returned `no_binding`; wrong namespace returned `not_bound`; a Pod request returned a tool error requiring stable ownership resolution. |
| Container | Final digest-pinned Python base plus hashed dependency lock built locally for linux/arm64. Full HTTP probe passed with UID/GID 65532, read-only root filesystem, all capabilities dropped, and no-new-privileges. An amd64 workplace build and image scan remain pending. |
| MCP body bytes | Complete JSON-RPC response bodies for eight probe calls: 2745, 1183, 1153, 1191, 1172, 349, 147, 184 bytes. Sum 8124 bytes; max 2745; below the 16384-byte test ceiling. Includes MCP content and structuredContent; excludes HTTP headers. |
| Manifest rendering | Optional extension rendered with resolved fixture inputs; renderer requires image digest, matching catalog cluster, distinct namespaces, no unresolved placeholders, and the four fixed Agent tools. Fixture image digest is intentionally fake; it was not deployed. |
| Public safety | Strict shared public-safety scan passed on the complete Radar bundle; Git whitespace check passed. |
| Cleanup | Temporary local HTTP process and test container removed. Built image and isolated Python environment retained locally for repeatability. |

## Pending cluster and Agent acceptance

- Kubernetes server dry-run, rollout, allowed/denied network clients and dedicated
  ServiceAccount permission checks on the actual policy-enforcing cluster.
- Current Radar Pod → stable owner evidence and a second disposable Pod resolving
  to the same guidance binding. Local tests only establish the binding rules,
  not Radar's ownership coverage.
- Installed kagent CRD compatibility, RemoteMCPServer discovery and Agent readiness.
- Real A2A tool trace across Radar then guidance, with source-cited response.
  No model request was made in this local run; yesterday's quota failure remains
  the last conversational result.
- Missing/stale guidance and unsupported-edge Agent behavior under the model,
  workload-specific diagnostic reads, and the workplace caller/auth boundary.
- Equivalent-case baseline versus guidance quality, time and actual model-token
  measurements. No savings claim is established by response-body byte bounds.

See [GUIDANCE-INTEGRATION.md](GUIDANCE-INTEGRATION.md) for image, Helm/Flux,
connection, deployment, trust-scope and acceptance guidance. No workplace
resources or existing Proxmox workloads were changed.
