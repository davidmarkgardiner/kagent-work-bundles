# Multi-cluster Kubernetes MCP work bundle

This bundle deploys one read-only Kubernetes MCP endpoint on a management
cluster, mounts a generated multi-context kubeconfig, fronts it with
agentgateway, and registers it with kagent. A single Agent and MCP server can
then address any approved AKS or Kubernetes cluster by passing its stable
`context` alias on each tool call.

## Deployment model

Use both deployment mechanisms through the supplied scripts:

- **Helm** installs and upgrades the upstream Kubernetes MCP server from the
  chart directory extracted from the approved GitHub ZIP.
- **Kustomize-rendered YAML** installs this bundle's NetworkPolicies,
  agentgateway backend/route/policy, the gateway kagent `RemoteMCPServer`, and the
  kagent Agent. The reader RBAC is applied separately to every target context.

Do not manually coordinate those pieces. `run-poc.sh` owns the order and uses
one customization file for the whole bundle.

Use this as the replacement for routine AKS workload and Kubernetes API
inspection. Keep AKS-MCP only for separately approved Azure managed-plane
operations. The exact boundary is documented in:

- [Kubernetes MCP operating boundary](KUBERNETES-MCP-OPERATING-BOUNDARY.md)
- [AKS-MCP operating boundary](AKS-MCP-OPERATING-BOUNDARY.md)

## Air-gapped inputs

On a connected staging machine, download the two source archives:

```bash
curl -fL -o kagent-public-kubernetes-mcp-bundle.zip \
  'https://github.com/davidmarkgardiner/kagent-public/archive/refs/heads/feat/kubernetes-mcp-multicluster-bundle.zip'
curl -fL -o kubernetes-mcp-server-v0.0.66.zip \
  'https://github.com/containers/kubernetes-mcp-server/archive/refs/tags/v0.0.66.zip'
```

The upstream archive contains the local chart at:

```text
kubernetes-mcp-server-0.0.66/charts/kubernetes-mcp-server
```

Also stage the release-matched public image tag:

```bash
docker pull quay.io/containers/kubernetes_mcp_server:v0.0.66
docker save --output kubernetes_mcp_server-v0.0.66.tar \
  quay.io/containers/kubernetes_mcp_server:v0.0.66
```

Transfer the two ZIP files and image archive through the approved air-gap
process. Inside the work environment:

1. extract both ZIP files;
2. load, scan, retag, and push the image into the internal registry;
3. set `CHART_REF` in `work-values.env` to the extracted local chart directory;
4. set `IMAGE_REGISTRY`, `IMAGE_REPOSITORY`, and `IMAGE_VERSION` to the
   internal image; and
5. retain the approved artifact checksums in the work-side receipt.

No deployment or verification script pulls a chart from the internet. Helm is
always given the local `CHART_REF`, and `deploy.sh` overrides every image value
from `work-values.env`. The checked-in `values.yaml` contains deliberately
invalid image placeholders so an uncustomized deployment fails instead of
pulling from a public registry.

## Proven topology

```text
credential refresh
  -> dedicated read-only identity on each target
  -> validated multi-context kubeconfig
  -> immutable Secret revision
  -> rolling kubernetes-mcp-server Deployment
       -> agentgateway fail-closed MCP backend and tool allowlist
            -> gateway kagent RemoteMCPServer
                 -> one context-explicit diagnostic Agent
```

The Agent request contains only a stable alias. Credentials never pass through
Argo Events, Agent prompts, or MCP tool arguments.

## One customization file

Create the one ignored workplace file:

```bash
cd work-agent-bundles/kubernetes-mcp-multicluster
cp work-values.env.template work-values.env
# Edit work-values.env once for the target environment.
```

`work-values.env` controls the management context, target context-to-alias
mappings, smoke markers, namespaces, existing Gateway, ModelConfig, internal
image location, local extracted chart directory, expected chart version,
approved image prefix, canonical tool allowlist, target API egress CIDRs,
replicas, CPU request, proof-token duration, and minimum accepted JWT lifetime.
It is excluded by `.gitignore`; never add credentials or kubeconfig content to
it.

Use unquoted values with no spaces. `SOURCE_CONTEXTS` and `SMOKE_CONTEXTS` are
comma-separated mappings. Use a local chart path without spaces.

`TARGET_API_CIDRS` has twelve deterministic slots for this fleet size. Supply
approved Kubernetes API IPs or aggregate network CIDRs and pad unused slots
with `0.0.0.0/32`. Default routes are rejected. The NetworkPolicy permits only
DNS plus TCP 443/6443 to those CIDRs. Set `APPROVED_IMAGE_PREFIX` to the
internal registry or project prefix; production image coordinates must match
it exactly unless the explicit home-lab escape hatch is enabled.

For AKS, prefer stable private-endpoint or approved private-network CIDRs.
Public AKS API FQDN addresses can change: resolve and revalidate every target
CIDR whenever fleet inventory, networking, private endpoints, or DNS changes,
and before every rollout that changes `TARGET_API_CIDRS`.

Kustomize reads the same file through `configMapGenerator` and replacements.
The resulting non-secret ConfigMap is stored in the POC namespace so the
applied customization is inspectable. Do not place credentials or sensitive
data in `work-values.env`.

Each `SOURCE_CONTEXTS` value maps an administrator/bootstrap kubeconfig context
to the stable alias exposed to the Agent. Each `SMOKE_CONTEXTS` marker must be
a non-secret node-name fragment unique to that target; it is used only at
runtime to prove there is no context crossover.

Prerequisites:

- `kubectl`, `helm`, `jq`, `openssl`, and `curl`;
- Python 3 and PyYAML for local manifest rendering and validation;
- the extracted Kubernetes MCP chart directory from the approved upstream ZIP;
- the Kubernetes MCP image already imported into the internal registry;
- bootstrap access to create the dedicated reader identity in every target;
- kagent `Agent` and `RemoteMCPServer` CRDs;
- agentgateway `AgentgatewayBackend` and `AgentgatewayPolicy` CRDs;
- Gateway API `HTTPRoute` and a programmed
  `agentgateway-system/ai-gateway`; and
- management-cluster network reachability to every target API.

## Run

After editing `work-values.env`:

```bash
./scripts/verify-bundle.sh
mkdir -p rendered
kubectl kustomize . > rendered/all.yaml  # optional review
./scripts/run-poc.sh
```

Every executable deployment script automatically loads the same ignored
`work-values.env` that Kustomize reads.

`run-poc.sh`:

1. verifies all source contexts and the installed kagent/agentgateway APIs;
2. runs `kubectl apply -k` for the customized namespace, default-deny
   NetworkPolicies, agentgateway resources, and kagent resources;
3. creates and verifies the same narrow reader identity in each target;
4. requests temporary reader tokens without logging them;
5. builds and validates one purpose-specific kubeconfig;
6. publishes it as a content-hashed immutable Secret;
7. deploys the internally hosted MCP image with the extracted local chart;
8. registers only the agentgateway path with kagent;
9. creates the gateway-backed read-only Agent; and
10. tests the MCP endpoint directly by port-forward and through agentgateway,
    then proves 20 alternating context calls with no crossover.

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
never edits a kubeconfig inside a running MCP pod. Every revision is labelled,
annotated with the earliest token expiry, and retained until the new rollout
succeeds. After success, the active and immediately previous revisions are
retained and older labelled revisions are deleted. If validation or rollout
fails, the previous revision remains active.

The included TokenRequest flow defaults to 24 hours and is a portable proof,
not the final AKS authentication implementation. It decodes each returned JWT
`exp` and rejects tokens with less than `MIN_TOKEN_VALIDITY_SECONDS` remaining,
so an API-server lifetime cap cannot pass silently.

For this proof flow, run the full refresh and deployment at least every 12
hours, alert when the active Secret's
`kubernetes-mcp-fleet/token-expires-at` annotation is less than six hours away,
and treat a missed refresh as an operational failure. A production CronJob must
implement that same SLA before this is used unattended.

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
REPO_ROOT=$(git rev-parse --show-toplevel)
"$REPO_ROOT/scripts/kagent-a2a-invoke.sh" \
  --context "$HOST_CONTEXT" \
  --agent kubernetes-mcp-fleet-agent \
  --text 'Use context {{STABLE_ALIAS_1}}. List v1 Node resources and report the node count. Do not use another context.'
```

The Agent is attached to the gateway `RemoteMCPServer`; it is not one Agent
per cluster. The selected alias is passed as the MCP tool's `context`
argument. There is deliberately no direct kagent `RemoteMCPServer`; the direct
path exists only as a local port-forward smoke test and cannot bypass the
agentgateway policy.

## Scale and rollback

Start with one replica. After capacity checks, exercise the production rollout:

```bash
# Change REPLICA_COUNT=3 in work-values.env, then run:
./scripts/deploy.sh "$secret_name"
```

The deploy script retains exactly the active and immediately previous
credential revisions. Before rolling back, verify that the previous Secret's
`kubernetes-mcp-fleet/token-expires-at` annotation is still in the future,
then use `helm rollback` to the preceding release revision. If that Secret is
expired or no previous revision exists, run `refresh-kubeconfig.sh` and
`deploy.sh` instead of attempting rollback.

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
