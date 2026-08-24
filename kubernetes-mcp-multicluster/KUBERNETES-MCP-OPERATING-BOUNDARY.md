# Kubernetes MCP operating boundary

## Purpose

Use Kubernetes MCP for Kubernetes API operations against clusters already
present in the mounted kubeconfig. One server can address multiple AKS or
non-AKS clusters; the caller selects a stable `context` on every tool call.

It is the preferred tool for workload and cluster data-plane inspection:

- namespaces, nodes, pods, workload controllers and Jobs;
- Kubernetes Events and selected pod logs;
- arbitrary approved Kubernetes resource reads; and
- separately approved Kubernetes mutations when an intentionally different
  write-capable endpoint and identity are deployed.

## Hard boundary

Kubernetes MCP does not discover AKS clusters from Azure, generate its own
credentials, repair Azure networking, operate subscriptions, resize Azure node
pools, upgrade the managed control plane, or change Azure resource settings.
Those are credential-job or Azure management-plane responsibilities.

The Agent supplies only `context`. It must never supply a token, kubeconfig,
subscription, resource group, API endpoint or certificate in its payload.

## Enforced POC controls

- One canonical eight-tool allowlist is rendered into the server, Agent and
  agentgateway policy; verification rejects any drift. The `config` toolset is
  omitted.
- `read_only=true`, `disable_destructive=true`, and Kubernetes RBAC deny writes.
- `cluster_auth_mode=kubeconfig` prevents caller Authorization headers from
  replacing the mounted target identity.
- Mounted kubeconfig is read-only and the pod ServiceAccount token is absent.
- Immutable Secret revisions and rolling updates replace in-pod file writes.
- Stateless mode supports ordinary service load balancing; start with one
  replica for verification and use three after production capacity checks.
- Only the gateway kagent registration exists. The direct endpoint is tested
  locally by port-forward but is not registered with kagent.
- Agentgateway repeats the tool allowlist and fails closed.
- NetworkPolicy admits only the agentgateway namespace and permits target API
  egress only to the configured CIDRs on TCP 443/6443.

The agentgateway policy is defense in depth, not the primary authorization
boundary. The server-side `read_only`/`disable_destructive` controls, exact
enabled-tool list, read-only mounted kubeconfig, and target-cluster reader RBAC
remain authoritative even if gateway policy enforcement is unavailable.

`pods_log` is intentionally enabled for triage but can expose application data
written to logs. Remove it from the MCP, agentgateway and Agent allowlists when
that risk is not acceptable.

## Credential ownership

The credential job owns target discovery, context generation, validation,
Secret publication and rollout initiation. Kubernetes MCP only reads the
completed file. A bad or incomplete refresh must leave the prior immutable
revision running.

Proof TokenRequest credentials are checked against their returned JWT expiry.
The proof rotation SLA is refresh at least every 12 hours with an alert at six
hours remaining. Successful rollouts prune inactive labelled Secret revisions;
teardown explicitly deletes every labelled revision before namespace removal.

For AKS, prefer `kubelogin -l workloadidentity` exec entries and a derived MCP
image containing a pinned `kubelogin`. The included TokenRequest workflow is a
portable proof mechanism and must not be treated as durable production
authentication.

## Escalation rule

If an incident requires an Azure resource or AKS managed-service change, stop
at diagnosis and route it to a separately authorized operator or AKS-MCP
workflow. Never add Azure credentials or broad write tools to this read-only
endpoint as an incident-time shortcut.
