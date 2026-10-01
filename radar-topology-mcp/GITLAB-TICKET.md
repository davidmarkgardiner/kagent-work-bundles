# Trial Radar topology MCP on one approved Kubernetes cluster

## Outcome

Provide a current Kubernetes relationship map to operators and a read-only
kagent Agent. Use Radar's existing collector, UI, and MCP server. Evaluate
relationship coverage before adding custom collection or a graph database.

## Implementation

- Use the `radar-topology-mcp` bundle, Radar chart/image 1.15.0, and a dedicated
  namespace with the selected inventory ServiceAccount.
- Render approved local inputs and validate the chart checksum, RBAC, and
  installed kagent CRDs. Use the existing accepted ModelConfig.
- Deliver permanent objects through the existing Flux repository. Start with an
  internal ClusterIP Service and controlled localhost UI access.
- Route kagent to `/mcp-readonly`; grant only `get_neighborhood` and `get_topology`.
- Review namespace scope, ConfigMap/workload data access, model egress, and actual
  NetworkPolicy enforcement with the platform/data owner.

## Acceptance

- [ ] Radar Pod Ready and UI opens a known namespace/resource relationship.
- [ ] Dedicated ServiceAccount lists approved inventory but cannot patch a
  Deployment, create a Pod/exec session, or read a Secret.
- [ ] Network access is limited to approved callers and denial is verified on
  the workplace CNI; no unauthenticated external UI or MCP route exists.
- [ ] Direct MCP probe returns the expected root and relationship within the
  requested node limit, with truncation/scope errors preserved.
- [ ] kagent RemoteMCPServer Accepted and discovers topology tools.
- [ ] New Agent Accepted/Ready/API-listed and an A2A request completes a real
  `get_neighborhood` call; its answer agrees with the direct evidence.
- [ ] Evidence identifies tested kinds, missing route hops, and unsupported reads.
- [ ] Rollback removes only the dedicated trial objects through their owning
  delivery path.

## Scope boundaries and follow-up

This phase does not prove fleet-wide graph storage, HA, live traffic/DNS health,
runtime skill mounting, KB retrieval, automated evaluation, or remediation execution.
Radar did not map the AgentgatewayBackend route hop in the local lab. Knowledge
bindings and the rubric are proposed artifacts plus inline Agent guidance.

Next phase: integrate approved knowledge lookup by stable workload identity,
cited source revisions, and an evaluator for the complete investigation. Keep
changes on reviewed workflow/GitOps execution identities.
