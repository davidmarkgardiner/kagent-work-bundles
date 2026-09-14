# Hardened homelab verification — 2026-08-24

## Result

```text
HOMELAB_SMOKE_OK contexts=2 secrets=1 mcp_shards=2 agents=2 a2a=2 cleanup=verified
```

The repeatable `scripts/homelab-smoke.sh` helper passed against the selected
management context and a separate Proxmox-hosted Kubernetes context. Endpoint,
certificate, token, node-address, and kubeconfig data are intentionally omitted.
The hardened run required exact discovered-tool sets, random target-only
markers, one successful marker-bearing function response per Agent, and
run-scoped cleanup.

## Proven live

| Check | Result |
|---|---|
| One-hour test identities | Two isolated ServiceAccounts were bound only to the built-in `view` role |
| Direct target access | Both generated source kubeconfigs could read the isolated smoke namespace |
| Candidate build | Two sources merged and validated as exactly two approved aliases |
| Secret publication | One existing Secret was atomically replaced with two single-context keys |
| AKS-MCP startup | Two v0.0.19 HTTP shards became Ready with read-only Secret mounts |
| Namespace boundary | Both shards started with only the run-scoped smoke namespace in `--allow-namespaces` |
| MCP discovery | Both RemoteMCPServers were Accepted and each discovered exactly `call_kubectl` |
| Agent readiness | Two fixed-target declarative Agents became Ready |
| A2A management route | Completed with one successful marker-bearing `call_kubectl` function response |
| A2A worker route | Completed with one successful marker-bearing `call_kubectl` function response |
| Installed CRD schemas | 18 placeholder-substituted resources passed server-side dry-run, including CronWorkflow, WorkflowTemplate, Agent, RemoteMCPServer, AgentgatewayBackend, HTTPRoute, AgentgatewayPolicy, RBAC, ConfigMaps, and Secrets |
| Cleanup | Test namespaces, bindings, Helm releases, RemoteMCPServers, Agents, tokens, and Secrets were absent after the helper exited |

## Redacted receipts

- [`management-smoke-receipt.json`](management-smoke-receipt.json) summarizes
  the 3,598-byte owner-only raw receipt, SHA-256
  `c19696afd7d7636f4edf8f7530106d108a29c68a07713a67284dc02a54156249`.
- [`worker-smoke-receipt.json`](worker-smoke-receipt.json) summarizes the
  3,549-byte owner-only raw receipt, SHA-256
  `6ea7bd07955f847a05f1f67a10fc9b72822165b3e7ff5a4a0d9938c34ca6eaef`.

Both terminal tasks reported `completed`; each history contained exactly one
`call_kubectl` function response with an `output` payload, no explicit error,
and the random marker that also appeared in the final Agent artifact. Raw
prompts, markers, and controller metadata are not committed.

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
- Live Agent Gateway authentication/authorization and NetworkPolicy denial;
  their rendered resources passed server-side validation against the installed
  homelab CRDs, but production keys were intentionally not created.
- KEDA load-based scaling and production alert delivery.
- All 10–12 work fleet targets.

Those remain explicit work-environment acceptance checks in
`GITLAB-TICKET.md`; this receipt must not be used to claim them complete.
