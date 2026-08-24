# AKS credential Job render evidence — 2026-08-24

## Proven in this checkout

- `verify-bundle.sh` passed with live server-side validation against the
  reachable homelab management cluster.
- A synthetic enabled Engineering configuration rendered distinct MCP,
  Agent, RemoteMCPServer, route, Secret, and CronJob names with
  `spec.suspend: false`.
- The AKS Helm variant rendered with no chart-created ServiceAccount, the
  configured Workload Identity ServiceAccount, token automount enabled, the
  Workload Identity pod label, and only the active `kubeconfig` Secret key
  mounted.
- The complete Kustomize output passed `kubectl apply --dry-run=server`.
- A disposable live namespace proved that reapplying the declarative empty
  Secret definition preserves kubeconfig data previously published through a
  resource-versioned Secret replacement; the namespace was then deleted.
- The existing live two-cluster MCP data path still passed direct and
  agentgateway smoke: eight tools, two contexts, 20 alternating calls, and
  zero crossover.
- The live kagent Agent remained `Accepted=True` and `Ready=True`; its gateway
  RemoteMCPServer discovered the expected eight tools.

## Not proven here

- No Azure subscription or AKS cluster was available in the homelab, so the
  UAMI token exchange, Azure cluster discovery, `az aks get-credentials`, and
  live AKS `kubelogin` calls remain work-environment acceptance tests.
- A fresh A2A Agent answer was attempted, but the configured model provider
  returned an account usage-limit error before tool execution. This was not an
  MCP, kagent readiness, or agentgateway discovery failure.
- Internal derived-image build, scan, registry push, and digest recording must
  be completed inside the approved work environment.
