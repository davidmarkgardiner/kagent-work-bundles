# Multi-cluster Kubernetes MCP work bundle

This bundle deploys one read-only Kubernetes MCP endpoint on a management
cluster, mounts a generated multi-context kubeconfig, fronts it with
agentgateway, and registers it with kagent. A single Agent and MCP server can
then address any approved AKS or Kubernetes cluster by passing its stable
`context` alias on each tool call.

## Deployment model

Use both deployment mechanisms:

- **Helm** installs and upgrades the upstream Kubernetes MCP server from the
  chart directory extracted from the approved GitHub ZIP.
- **Kustomize-rendered YAML** installs this bundle's NetworkPolicies,
  agentgateway backend/route/policy, the gateway kagent `RemoteMCPServer`, and the
  kagent Agent. The reader RBAC is applied separately to every target context.

The durable AKS path uses a Kubernetes CronJob for credential refresh. The
local `run-poc.sh` remains only for the two-cluster homelab proof.

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

Also stage the release-matched public image tag and approved, pinned Linux
tool binaries. The MCP image needs only `kubelogin`; the credential-refresh
Job image separately needs Azure CLI, `kubectl`, `kubelogin`, `jq`, and Bash.
Follow the exact pinned artifact, checksum, offline build, and pipeline proof in
the [work-side Kubernetes MCP image guide](mcp-image/README.md):

```bash
docker pull quay.io/containers/kubernetes_mcp_server:v0.0.66
docker save --output kubernetes_mcp_server-v0.0.66.tar \
  quay.io/containers/kubernetes_mcp_server:v0.0.66
```

Transfer the two ZIP files and image archive through the approved air-gap
process. Inside the work environment:

1. extract both ZIP files;
2. load and scan the upstream image, then follow
   [`mcp-image/README.md`](mcp-image/README.md) to build and prove the offline
   derived MCP image; build the refresh image separately from
   `credential-refresh-image/`;
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
  -> AKS-MCP UAMI through its existing federated ServiceAccount
  -> discover only the configured environment subscriptions
  -> kubelogin Workload Identity contexts
  -> validated multi-context kubeconfig
  -> named Secret updated through namespace-scoped RBAC
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
replicas, CPU request, AKS environment subscription inventory, UAMI and
ServiceAccount names, refresh schedule, and image, proof-token duration, and
minimum accepted JWT lifetime.
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

`AZURE_IDENTITY_EGRESS_CIDRS` supplies four separate TCP 443 slots for the MCP
pod's Entra token exchange. Prefer an approved egress proxy or Azure Firewall
CIDR because standard Kubernetes NetworkPolicy cannot match FQDNs. Default
routes are rejected. The refresh Job runs in the existing AKS-MCP namespace
and must also be allowed to reach Azure management endpoints and target APIs by
that namespace's own egress controls.

Kustomize reads the same file through `configMapGenerator` and replacements.
The resulting non-secret ConfigMap is stored in the POC namespace so the
applied customization is inspectable. Do not place credentials or sensitive
data in `work-values.env`.

Each `SOURCE_CONTEXTS` value maps an administrator/bootstrap kubeconfig context
to the stable alias exposed to the Agent. Each `SMOKE_CONTEXTS` marker must be
a non-secret node-name fragment unique to that target; it is used only at
runtime to prove there is no context crossover.

For work, deploy one independently named bundle instance per environment. An
Engineering instance and a Dev instance must use different `HOST_NAMESPACE`,
`MCP_NAME`, `KAGENT_AGENT_NAME`, `REMOTE_MCP_NAME`,
`AGENTGATEWAY_MCP_PATH`, `AGENTGATEWAY_MCP_URL`,
`KUBECONFIG_SECRET_NAME`, and `CREDENTIAL_REFRESH_*_NAME` values. Give each
instance only its environment's comma-separated `AZURE_SUBSCRIPTION_IDS`.
Keep one `work-values.env` beside each Kustomization; do not combine the two
inventories into a tenant-wide discovery role.

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

## AKS Workload Identity setup

The refresh CronJob runs in `AKS_MCP_WORKLOAD_NAMESPACE` as the existing
`AKS_MCP_SERVICE_ACCOUNT`. It therefore reuses AKS-MCP's current federated
identity credential and UAMI without creating another federation for the Job.

The Kubernetes MCP pod runs under
`MCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT` in `HOST_NAMESPACE`. Create one
additional federated identity credential on the same UAMI with the exact
management-cluster issuer, audience `api://AzureADTokenExchange`, and subject:

```text
system:serviceaccount:{{HOST_NAMESPACE}}:{{MCP_WORKLOAD_IDENTITY_SERVICE_ACCOUNT}}
```

This second federation is required because Azure federation matches the exact
namespace and ServiceAccount subject. No federation is needed on destination
clusters: those APIs are reached by the central management-cluster workload.

Grant the UAMI only the Azure permissions required to list the configured AKS
clusters and call the cluster-user credential action. Separately grant that
identity the intended read-only Azure Kubernetes authorization on every target
cluster. Never use `--admin`.

## Kubernetes-native AKS credential refresh

Set `AKS_CREDENTIAL_REFRESH_ENABLED=1` and
`CREDENTIAL_REFRESH_SUSPEND=false`. Then apply the one customization:

```bash
kubectl --context {{MANAGEMENT_CONTEXT}} apply -k .
```

This creates the empty named Secret, the Kubernetes MCP Workload Identity
ServiceAccount, a resource-name-scoped publisher Role/RoleBinding, and the
daily CronJob. The publisher binding points to the existing AKS-MCP
ServiceAccount across namespaces. It can update only the named Secret and
patch only the named MCP Deployment; it cannot list or create Secrets.

To run the first refresh immediately instead of waiting for the daily schedule:

```bash
kubectl --context {{MANAGEMENT_CONTEXT}} -n {{AKS_MCP_WORKLOAD_NAMESPACE}} \
  create job --from=cronjob/{{CREDENTIAL_REFRESH_NAME}} \
  {{CREDENTIAL_REFRESH_NAME}}-bootstrap
kubectl --context {{MANAGEMENT_CONTEXT}} -n {{AKS_MCP_WORKLOAD_NAMESPACE}} \
  wait --for=condition=complete job/{{CREDENTIAL_REFRESH_NAME}}-bootstrap \
  --timeout=30m
```

That is a Kubernetes Job invocation, not a local credential script. The pod:

1. exchanges the projected token for the existing AKS-MCP UAMI;
2. lists all AKS clusters in only `AZURE_SUBSCRIPTION_IDS`;
3. retrieves non-admin exec-format kubeconfigs and converts them with
   `kubelogin -l workloadidentity`;
4. uses the AKS cluster name as the stable context expected in the payload and
   fails if that name is duplicated across the environment subscriptions;
5. rejects static tokens, client keys, insecure TLS, or duplicate contexts;
6. checks `/readyz`, confirms pod-list access, and confirms Secret denial on
   every context;
7. replaces the named Secret only after the whole fleet passes; and
8. patches the MCP pod-template credential hash and waits for a healthy
   rollout. On rollout failure it restores the preceding kubeconfig.

After the bootstrap Job succeeds, deploy the local Helm chart once:

```bash
./scripts/deploy.sh
./scripts/register.sh
./scripts/smoke.sh
```

`deploy.sh` does not fetch credentials. In AKS mode it mounts the stable Secret,
selects the Kustomize-created Workload Identity ServiceAccount, and proves the
derived MCP image contains `kubelogin`. Subsequent credential rotation is
entirely owned by the CronJob.

The stable Secret is intentionally mutable in this AKS workflow. It contains
CA data, target metadata, and `kubelogin` exec entries—not a cached bearer
token or client key. Kubernetes projects Secret updates atomically, and the
Job also forces a Deployment rollout. Only the current `kubeconfig` key is
mounted; the preceding validated value is retained in the same Secret solely
for automatic rollback.

## Homelab credential refresh

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

The included local TokenRequest flow defaults to 24 hours and is a portable proof,
not the final AKS authentication implementation. It decodes each returned JWT
`exp` and rejects tokens with less than `MIN_TOKEN_VALIDITY_SECONDS` remaining,
so an API-server lifetime cap cannot pass silently.

For this proof flow, run the full refresh and deployment at least every 12
hours, alert when the active Secret's
`kubernetes-mcp-fleet/token-expires-at` annotation is less than six hours away,
and treat a missed refresh as an operational failure. This expiry contract
does not apply to the AKS Workload Identity exec kubeconfig, which obtains a
short-lived token on demand.

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
8. atomically update the named Secret while retaining the preceding value; and
9. roll the MCP Deployment.

Do not use `az aks get-credentials --admin`, store Azure access tokens in the
kubeconfig, grant the refresh job general Secret-read access, or partially
replace the live fleet file.

The supplied `mcp-image/` and `credential-refresh-image/` Dockerfiles are
offline build contracts. Both require reviewed, pinned inputs and perform no
download during the image build.

## kagent behavior check

After registration, invoke the Agent through the repository A2A helper:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
"$REPO_ROOT/scripts/kagent-a2a-invoke.sh" \
  --context "$HOST_CONTEXT" \
  --agent {{KAGENT_AGENT_NAME}} \
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

The AKS refresh Job keeps the preceding kubeconfig in the unmounted
`kubeconfig.previous` Secret key and restores it automatically if the rollout
does not become available. The homelab proof retains N and N-1 immutable
revisions as described above.

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

The derived-image follow-up is in
[evidence/derived-image-live-homelab-2026-08-25.md](evidence/derived-image-live-homelab-2026-08-25.md).
It proves that the exact pinned Linux `kubelogin` binary runs in the non-root
MCP image and that direct and agentgateway MCP reads still work. Azure token
exchange remains a work-AKS acceptance gate.
