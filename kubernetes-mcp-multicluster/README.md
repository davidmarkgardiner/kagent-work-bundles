# Multi-cluster Kubernetes MCP work bundle

This bundle deploys one read-only Kubernetes MCP endpoint on a management
cluster, mounts a generated multi-context kubeconfig, fronts it with
agentgateway, and registers it with kagent. A single Agent and MCP server can
then address any approved AKS or Kubernetes cluster by passing its stable
`context` alias on each tool call.

Use this as the replacement for routine AKS workload and Kubernetes API
inspection. Keep AKS-MCP only for separately approved Azure managed-plane
operations. The exact boundary is documented in:

- [Kubernetes MCP operating boundary](KUBERNETES-MCP-OPERATING-BOUNDARY.md)
- [AKS-MCP operating boundary](AKS-MCP-OPERATING-BOUNDARY.md)

## Pull coordinates

The tested image tag is:

```text
quay.io/containers/kubernetes_mcp_server:latest
```

The deployment uses the published Helm chart:

```text
oci://ghcr.io/containers/charts/kubernetes-mcp-server
chart version: 0.1.0
```

`latest` is mutable. Import it into the approved internal registry, complete
the work-side validation, and then pin the resulting internal digest or
immutable internal tag.

## Proven topology

```text
credential refresh
  -> dedicated read-only identity on each target
  -> validated multi-context kubeconfig
  -> immutable Secret revision
  -> rolling kubernetes-mcp-server Deployment
       -> direct kagent RemoteMCPServer
       -> agentgateway fail-closed MCP backend and tool allowlist
            -> gateway kagent RemoteMCPServer
                 -> one context-explicit diagnostic Agent
```

The Agent request contains only a stable alias. Credentials never pass through
Argo Events, Agent prompts, or MCP tool arguments.

## Configuration

Replace every placeholder locally; do not commit the resolved values:

```bash
export HOST_CONTEXT='{{MANAGEMENT_KUBECONFIG_CONTEXT}}'
export SOURCE_CONTEXTS='{{SOURCE_CONTEXT_1}}={{STABLE_ALIAS_1}} {{SOURCE_CONTEXT_2}}={{STABLE_ALIAS_2}}'
export SMOKE_CONTEXTS='{{STABLE_ALIAS_1}}={{UNIQUE_NODE_MARKER_1}} {{STABLE_ALIAS_2}}={{UNIQUE_NODE_MARKER_2}}'
```

Each `SOURCE_CONTEXTS` entry maps an administrator/bootstrap kubeconfig
context to the stable alias exposed to the Agent. Each `SMOKE_CONTEXTS`
marker must be a non-secret node-name fragment unique to that target; it is
used only at runtime to prove there is no context crossover.

Prerequisites:

- `kubectl`, `helm`, `jq`, `openssl`, `curl`, Node.js and `npx`;
- bootstrap access to create the dedicated reader identity in every target;
- kagent `Agent` and `RemoteMCPServer` CRDs;
- agentgateway `AgentgatewayBackend` and `AgentgatewayPolicy` CRDs;
- Gateway API `HTTPRoute` and a programmed
  `agentgateway-system/ai-gateway`; and
- management-cluster network reachability to every target API.

## Run

From the repository root:

```bash
cd work-agent-bundles/kubernetes-mcp-multicluster
./scripts/verify-bundle.sh
./scripts/run-poc.sh
```

`run-poc.sh`:

1. verifies all source contexts and the installed kagent/agentgateway APIs;
2. applies an isolated namespace and default-deny NetworkPolicies;
3. creates and verifies the same narrow reader identity in each target;
4. requests temporary reader tokens without logging them;
5. builds and validates one purpose-specific kubeconfig;
6. publishes it as a content-hashed immutable Secret;
7. deploys the MCP server from the public OCI chart;
8. registers direct and agentgateway paths with kagent;
9. creates the gateway-backed read-only Agent; and
10. proves exact tool discovery and 20 alternating context calls with no
    crossover.

The server exposes exactly:

```text
events_list
namespaces_list
pods_get
pods_list
pods_list_in_namespace
pods_log
resources_get
resources_list
```

The `config` toolset is deliberately omitted because configuration inspection
can reveal kubeconfig authentication material.

## Credential refresh

Run the credential steps independently when testing rotation:

```bash
./scripts/install-readers.sh
secret_name=$(./scripts/refresh-kubeconfig.sh)
./scripts/deploy.sh "$secret_name"
```

The script creates a new immutable Secret revision and rolls the Deployment. It
never edits a kubeconfig inside a running MCP pod. If validation fails, the
previous revision remains active.

The included TokenRequest flow defaults to 24 hours and is a portable proof,
not the final AKS authentication implementation.

## Production AKS refresh contract

Run the scheduled refresh under an Azure Workload Identity-enabled
ServiceAccount. For each approved inventory record it must:

1. select the subscription explicitly;
2. retrieve the non-admin AKS kubeconfig in exec format;
3. use `kubelogin -l workloadidentity`;
4. rewrite the context to the stable payload alias;
5. reject insecure TLS, duplicates, and unexpected contexts;
6. validate API readiness and the positive/negative RBAC matrix;
7. merge only after the complete fleet passes;
8. publish a new immutable Secret; and
9. roll the MCP Deployment.

Do not use `az aks get-credentials --admin`, store Azure access tokens in the
kubeconfig, grant the refresh job general Secret-read access, or partially
replace the live fleet file.

The upstream image does not include `kubelogin`. The AKS variant therefore
needs a reviewed derived image containing a pinned `kubelogin`, or an
equivalent reviewed credential helper arrangement.

## kagent behavior check

After registration, invoke the Agent through the repository A2A helper:

```bash
scripts/kagent-a2a-invoke.sh \
  --context "$HOST_CONTEXT" \
  --agent kubernetes-mcp-fleet-agent \
  --text 'Use context {{STABLE_ALIAS_1}}. List v1 Node resources and report the node count. Do not use another context.'
```

The Agent is attached to the gateway `RemoteMCPServer`; it is not one Agent
per cluster. The selected alias is passed as the MCP tool's `context`
argument.

## Scale and rollback

Start with one replica. After capacity checks, exercise the production rollout:

```bash
REPLICA_COUNT=3 ./scripts/deploy.sh "$secret_name"
```

Roll back by pointing the Deployment at the previous immutable Secret revision.
Remove only this bundle's named resources with:

```bash
./scripts/teardown.sh
```

The teardown does not use broad selectors and does not delete unrelated MCP,
kagent, or agentgateway resources.

## Evidence boundary

The sanitized home-lab receipt is in
[evidence/live-homelab-2026-08-24.md](evidence/live-homelab-2026-08-24.md).
It proves the Kubernetes MCP, kagent, and agentgateway data path. It does not
claim that the Azure Workload Identity/`kubelogin` refresh has been tested
against a real AKS target.
