# Local verification receipt

Date: 2026-09-30. Scope: disposable kind cluster, Radar 1.15.0, kagent 0.10.1
Go runtime. Workplace values and raw model/provider responses are excluded.

| Gate | Result |
|---|---|
| Config render | Real non-secret lab config rendered; shipped unresolved model placeholder must be filled before rendering. |
| Archive | Radar 1.15.0 package SHA256 matched `versions.json`. |
| Helm/Flux shape | Helm rendered successfully; custom verifier confirmed one Pod, selected inventory reads, internal Service, matching Flux values, and two Agent tools. Flux reconciliation was not tested. |
| Guard checks | Verifier rejected an injected workload mutation permission; renderer rejected an unresolved ModelConfig. Bundled canonical helper hashes matched the source scripts. |
| Kubernetes schema | Namespace, access, NetworkPolicy, Helm resources, and kagent objects passed server validation in the lab. Namespace must exist before dry-running namespaced resources. |
| Narrow profile | Installed the bundle's custom RBAC and chart values in a separate disposable namespace; Deployment Ready. |
| Permission checks | list Pods=yes; patch Deployments=no; read Secrets=no; create Pods=no; create pods/exec=no for the dedicated ServiceAccount. |
| MCP probe | `/mcp-readonly`: Radar 1.15.0, 25 tools with `readOnlyHint=true`, one Service neighborhood with two nodes, one `exposes` edge, no truncation, within a ten-node request limit. |
| kagent | RemoteMCPServer Accepted; Agent Accepted/Ready/API-listed with only two allowed topology tools. |
| A2A | Retried the bounded prompt; model provider again returned quota/usage limit before tool use. Completed conversational Agent behavior remains unproven. |
| Network enforcement | Manifest rendered/applied; enforcement not proven because the kind lab does not establish a policy-enforcing CNI. Workplace denial checks remain required. |
| Knowledge | Catalog/procedure/rubric files are handoff artifacts. No KB server, runtime skill loader, graph-guidance joins, or automatic evaluator was deployed. |

The separate bundle test installation is cleaned up after checks. The earlier
Radar evaluation remains the browser demonstration. No workplace resources were
changed. See [README.md](README.md) for the workplace acceptance steps.
