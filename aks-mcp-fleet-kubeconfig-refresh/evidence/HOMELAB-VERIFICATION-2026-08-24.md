# Homelab verification — 2026-08-24

## Result

```text
HOMELAB_SMOKE_OK contexts=2 secrets=1 mcp_shards=2 agents=2 a2a=2
```

The repeatable `scripts/homelab-smoke.sh` helper passed against the selected
management context and a separate Proxmox-hosted Kubernetes context. Endpoint,
certificate, token, node-address, and kubeconfig data are intentionally omitted.
This run predates the helper's exact discovered-tool and raw function-response
gates, so its terminal marker is retained as historical evidence rather than a
complete trace-backed A2A receipt. Repeat the hardened helper before work use.

## Proven live

| Check | Result |
|---|---|
| One-hour test identities | Two isolated ServiceAccounts were bound only to the built-in `view` role |
| Direct target access | Both generated source kubeconfigs could read the isolated smoke namespace |
| Candidate build | Two sources merged and validated as exactly two approved aliases |
| Secret publication | One existing Secret was atomically replaced with two single-context keys |
| AKS-MCP startup | Two v0.0.19 HTTP shards became Ready with read-only Secret mounts |
| MCP discovery | Both RemoteMCPServers were Accepted; exact discovery JSON was not retained by this run |
| Agent readiness | Two fixed-target declarative Agents became Ready |
| A2A management route | Alias-routed request returned `TARGET_OK`; no raw tool-call trace was retained |
| A2A worker route | Alias-routed request returned `TARGET_OK`; no raw tool-call trace was retained |
| Installed CRD schemas | Placeholder-substituted bundle passed server-side dry-run for CronWorkflow, WorkflowTemplate, Agent, RemoteMCPServer, RBAC, ConfigMaps, and Secret |
| Cleanup | Test namespaces, bindings, Helm releases, RemoteMCPServers, Agents, tokens, and Secrets were absent after the helper exited |

The pulled AKS-MCP v0.0.19 image resolved to digest
`sha256:f6ee94b45dbb5a3e5e5bfd6cc80d96389527459c2940c5dc9cb2976ed3c26072`
in this test. Work deployment must independently approve and pin its digest.

## Findings that changed the design

1. AKS-MCP v0.0.19 refuses non-loopback HTTP without OAuth or an explicit
   allowed host. The chart now supports `app.allowedHosts`, and each shard
   allowlists only its Service DNS name.
2. The v0.0.19 `mcp-kubernetes` v0.0.14 security validator intentionally blocks
   `--context`, `--kubeconfig`, `--server`, token, and certificate flags. A
   read-only Agent also cannot run `kubectl config use-context`. Therefore a
   single stock AKS-MCP cannot safely select a context from the request.
3. The management node was at 99% requested CPU during the proof. The ephemeral
   smoke pods used 1m requests without changing existing workloads. Production
   sizing must use normal measured requests rather than these smoke-only values.
4. One A2A completion returned no text during an earlier attempt. The helper
   permits one bounded retry and fails after the second attempt.

## Not proven here

- Azure Workload Identity, Azure RBAC, `az aks get-credentials`, or kubelogin.
- The approved production builder/router images.
- A live scheduled CronWorkflow or Flux field-ignore configuration.
- KEDA load-based scaling and production alert delivery.
- All 10–12 work fleet targets.
- Exact `call_kubectl` discovery and marker-bearing function-response traces for
  the historical A2A calls.

Those remain explicit work-environment acceptance checks in
`GITLAB-TICKET.md`; this receipt must not be used to claim them complete.
