# AKS-MCP fleet kubeconfig refresh

This bundle replaces per-request `az aks get-credentials` writes with one
morning Argo `CronWorkflow`. It builds and proves a fresh multi-context
candidate, splits it into one current-context file per cluster, and atomically
stores those files as keys in one Secret. Each fixed-target AKS-MCP/Agent pair
mounts only its key. The incoming Argo job validates `clusterAlias` against an
allowlist and routes the payload to the matching Agent.

The old Secret and running pods remain untouched if any cluster fails. A
periodic blind pod recycle is therefore unnecessary as a credential-repair
mechanism; normal KEDA scaling, Kubernetes rescheduling, and a controlled
rollout after a verified credential change cover separate lifecycle concerns.

## Flow

1. `aks-fleet-registry` holds approved AKS aliases and Azure lookup fields.
2. At 05:00 Europe/London, Argo starts one refresh because concurrency is
   `Forbid`.
3. The workflow uses Azure Workload Identity to establish an ephemeral Azure
   CLI session in `/work/.azure`, verifies the active account, and uses an
   approved builder image to run `az aks get-credentials --format exec` for
   each cluster into a new file.
4. The script converts authentication to `kubelogin` workload identity, removes
   the candidate's `current-context`, rejects aliases outside the registry and
   embedded static credentials, and checks namespace plus read-only pod access
   on every context.
5. If the SHA-256 is unchanged, the workflow exits without touching the Secret
   or pods. If changed, it server-validates and replaces the Secret, restarts
   every named AKS-MCP shard, and waits for rollouts in bounded parallel batches.
6. `aks-fleet-agent-router` maps the payload alias to `aks-<alias>-agent`. That
   Agent has exactly one AKS-MCP tool source, and its MCP pod sees exactly one
   current context.

## Why this shape

- Credential acquisition and Secret publication remain one fleet operation,
  while execution identity and failure scope stay isolated per cluster.
- Nothing writes to the kubeconfig inside a running MCP pod. Secret volumes are
  read-only and kubelet refresh semantics are not relied upon: a changed Secret
  deliberately rolls the pods.
- A candidate is all-or-nothing. One broken or rebuilt cluster cannot publish a
  partially valid fleet file over the last-known-good copy.
- The refresher can update only the named Secret and restart only the named
  shard Deployments. Each read-only Agent exposes only `call_kubectl`.

The requested one-Agent/one-MCP/multi-context shape is not supported by stock
AKS-MCP v0.0.19. Its `mcp-kubernetes` security validator intentionally rejects
`--context`, `--kubeconfig`, `--server`, token, and certificate flags because
they can redirect API traffic or inject credentials. Read-only mode also blocks
`kubectl config use-context`. A shared writable current context would introduce
cross-request races. The supported answer is therefore one agent/MCP pair per
cluster, with one shared refresh workflow and one multi-key Secret. Building a
separate allowlisted fleet-router MCP is a possible future alternative, but it
would be a new component rather than stock AKS-MCP.

## Files

| Path | Purpose |
|---|---|
| `manifests/00-core.yaml` | Workload Identity SA, narrow RBAC, bootstrap Secret, production registry, sanitized agent routing |
| `manifests/01-cronworkflow.yaml` | Morning Argo schedule and ephemeral build pod |
| `manifests/02-agent.yaml` | Repeatable fixed-target RemoteMCPServer and Agent template |
| `manifests/03-argo-agent-router.yaml` | Fail-closed Argo payload-to-Agent routing template |
| `aks-mcp-values.yaml` | Per-alias, three-replica, read-only AKS-MCP shard values |
| `scripts/refresh-fleet-kubeconfig.sh` | Candidate, validation, atomic publication, and rollout logic |
| `scripts/homelab-smoke.sh` | Reversible two-cluster MCP and A2A proof using one-hour read-only identities |
| `scripts/verify-bundle.sh` | Offline test, render, lint, and public-safety gate |

## Production installation

1. Build and approve an immutable `{{FLEET_KUBECONFIG_BUILDER_IMAGE}}`
   containing `az`, `kubectl`, `kubelogin`, `jq`, Bash, and GNU coreutils.
2. Replace every `{{PLACEHOLDER}}`. Add one registry/routing row and render one
   `02-agent.yaml` plus `aks-mcp-values.yaml` instance per cluster. Context
   aliases must be unique DNS-style lowercase names.
3. Configure Azure Workload Identity. The identity needs AKS cluster-user
   credential read access on the approved fleet; never use `--admin`. Create a
   federated credential for the refresh subject
   `system:serviceaccount:aks-mcp:fleet-kubeconfig-refresher` and one for every
   shard subject `system:serviceaccount:aks-mcp:aks-mcp-{{CLUSTER_ALIAS}}`, all
   using the management cluster OIDC issuer and audience
   `api://AzureADTokenExchange`. Each shard ServiceAccount is annotated with
   `{{AZURE_CLIENT_ID}}`; its management-cluster token automount and chart RBAC
   are disabled because kubelogin uses the projected workload-identity token.
4. Bootstrap `manifests/00-core.yaml`, then configure Flux to ignore only
   `/data` and the kubeconfig hash annotation on the named Secret. Do not
   make the whole Secret unmanaged.
5. Install one shard for each alias, then the workflows and fixed-target Agents:

   ```bash
   helm upgrade --install "aks-mcp-{{CLUSTER_ALIAS}}" ../../platform/aks-mcp/chart \
     --namespace aks-mcp --create-namespace -f aks-mcp-values.yaml
   kubectl apply -k .
   ```

6. Submit the template once before enabling the schedule:

   ```bash
   argo submit --from cronwf/aks-mcp-fleet-kubeconfig-refresh -n aks-mcp --watch
   kubectl get secret aks-mcp-fleet-kubeconfig -n aks-mcp \
     -o jsonpath='{.metadata.annotations.platform\.example\.com/kubeconfig-sha256}'
   kubectl rollout status deployment/aks-mcp-{{CLUSTER_ALIAS}} -n aks-mcp
   ```

7. Submit the router with an explicit JSON payload; it chooses the allowlisted
   fixed-target Agent rather than asking AKS-MCP to switch context:

   ```json
   {"clusterAlias":"{{CLUSTER_ALIAS}}","namespace":"{{ALLOWED_NAMESPACE}}","question":"Which pods are not Ready?"}
   ```

## Rebuilt or unavailable cluster

The normal morning run already requests current AKS user credentials and tests
the resulting API context, so a rebuilt cluster is picked up automatically when
its registry identity is unchanged. If the cluster name/resource group changes,
update the registry through GitOps first. If one target is unavailable, alert on
the failed Workflow; do not replace the valid fleet Secret. An operator can
rerun the CronWorkflow after the cluster is restored.

Suggested alerts are: last successful refresh older than 30 hours, any failed
refresh, Secret hash unchanged for an unexpectedly long fleet migration, or an
AKS-MCP rollout that does not complete in five minutes.

## Homelab proof

The smoke helper never copies administrator kubeconfigs into AKS-MCP. It creates
one-hour ServiceAccount tokens bound to Kubernetes' built-in `view` role in an
isolated namespace on two explicit contexts, builds one candidate and one
two-key Secret, starts two fixed-target AKS-MCP/Agent pairs, and performs one
A2A call per alias. Each call must return a random target-only marker and retain
exactly one successful marker-bearing `call_kubectl` function response. The
helper also requires each RemoteMCPServer to discover exactly that one tool.
All namespaces, bindings, Helm releases, Agents, and RemoteMCPServers are
run-scoped, and the helper removes them by default.

```bash
scripts/homelab-smoke.sh \
  --management-context "{{MANAGEMENT_CONTEXT}}" \
  --worker-context "{{WORKER_CONTEXT}}"
```

Static sources and embedded tokens are test-only escape hatches requiring both
`ALLOW_STATIC_SOURCES=true` and `ALLOW_STATIC_CREDENTIALS=true`. They are not
set in the production CronWorkflow.

## Version boundary

The repository's HTTP chart cannot use AKS-MCP v0.0.20 because that release is
stdio-only. This bundle pins v0.0.19 for the compatibility proof. Before work
deployment, pin the approved image digest and repeat RemoteMCPServer discovery
plus A2A testing. Do not silently float the tag.

## Verification

```bash
scripts/verify-bundle.sh
```

Offline verification does not prove Azure RBAC, private network routes, the
approved builder image, or installed-version CRD compatibility. Record those
receipts in the work environment without kubeconfig content, tokens, endpoints,
tenant IDs, or subscription IDs.
