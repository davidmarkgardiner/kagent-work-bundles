# AKS MCP — deployment and authentication

This directory deploys [AKS-MCP](https://github.com/Azure/aks-mcp), the MCP
server that exposes Azure-aware Kubernetes tools such as `call_kubectl` to
kagent. It documents the repository's intended identity model; every value
that is specific to an Azure environment remains a placeholder.

## The important distinction

Azure workload identity answers **which Azure identity the AKS-MCP process can
become**. It does not by itself grant access to Kubernetes APIs, make remote
clusters reachable, or give an agent the MCP tool.

```
kagent agent
  └─ RemoteMCPServer / ToolCatalogEntry ──HTTP──► AKS-MCP Service
                                                   │
                                                   ├─ Kubernetes ServiceAccount + Kubernetes RBAC
                                                   │     └─ Kubernetes API operations
                                                   │
                                                   └─ Azure Workload Identity → UAMI
                                                         └─ Azure Resource Manager / AKS operations
```

The agent does not mount the tool. It calls the in-cluster MCP endpoint. The
bootstrap catalog uses:

```text
http://aks-mcp.aks-mcp.svc.cluster.local:8000/mcp
```

See [`infra/byo-kagent/bootstrap-catalog/toolcatalogentry-aks-mcp.yaml`](../../infra/byo-kagent/bootstrap-catalog/toolcatalogentry-aks-mcp.yaml).

## How workload identity reaches the AKS-MCP container

When `workloadIdentity.enabled=true`, the chart:

1. annotates the AKS-MCP ServiceAccount with
   `azure.workload.identity/client-id: "{{UAMI_CLIENT_ID}}"`;
2. labels the pod template `azure.workload.identity/use: "true"`;
3. relies on the AKS workload-identity webhook to inject the projected
   service-account token and Azure identity environment into the pod at
   admission time; and
4. lets Azure AD exchange that projected token for an access token for the
   UAMI, provided a matching federated credential exists.

The projected token is injected by AKS; it is not a bespoke AKS-MCP volume in
this chart. `kubeconfig.enabled` is separate and only mounts the named
Kubernetes Secret at `/home/mcp/.kube`.

The trust tuple must match exactly:

```text
issuer:   the AKS cluster's OIDC issuer URL
subject:  system:serviceaccount:aks-mcp:aks-mcp
audience: api://AzureADTokenExchange
UAMI:     {{UAMI_NAME}}
```

The ASO examples in
[`infra/workload-identity/`](../../infra/workload-identity/README.md) show the
same issuer-and-subject mechanics for per-cluster workloads. For the central
deployment described below, use the **management-cluster issuer** instead.

## Deployment models

| Model | Where AKS-MCP runs | Federation required | What remains to configure |
|---|---|---|---|
| Per-worker-cluster | Each worker cluster | That worker cluster's OIDC issuer → its local `aks-mcp` ServiceAccount | UAMI Azure roles and local Kubernetes RBAC |
| Central MCP | Management cluster | The management cluster's OIDC issuer → the central `aks-mcp` ServiceAccount | UAMI Azure roles, remote-cluster credential/context or supported connection path, and remote Kubernetes authorization |

## Recommended central-MCP topology

The intended design is one AKS-MCP deployment on the management cluster which
reaches worker-cluster APIs. In this model, create **one federated credential
on the UAMI for the management cluster's issuer**:

```text
issuer:   {{MANAGEMENT_CLUSTER_OIDC_ISSUER}}
subject:  system:serviceaccount:aks-mcp:aks-mcp
audience: api://AzureADTokenExchange
UAMI:     {{AKS_MCP_UAMI_NAME}}
```

Do not add worker-cluster issuer federations merely because the central MCP
will call those clusters. A federated credential is only needed for a cluster
that issues the token used by a workload becoming the UAMI. Here, that
workload is AKS-MCP and it runs on the management cluster.

```
management cluster                                      worker cluster
──────────────────                                      ──────────────
AKS-MCP pod (SA: aks-mcp/aks-mcp)
  │ projected token issued by management OIDC
  ▼
UAMI token exchange
  │ Azure and Kubernetes authorization for target cluster
  └──────────────────────────────────────────────────► worker API server
                                                       │
                                                       ▼
                                                allowed read-only actions
```

Worker-cluster federation is only required if another workload running in a
worker cluster also needs to become that UAMI, such as a per-worker MCP or an
Azure-calling operator. The central deployment option is separately called out
in [`observability/PRODUCTION-READINESS.md`](../../observability/PRODUCTION-READINESS.md).

## Required authorization bindings

Federation is authentication only. Configure both authorization planes:

| Plane | Required binding | Why |
|---|---|---|
| Azure | Assign the UAMI least-privilege Azure roles at the AKS resource or resource-group scope. `Reader` supports discovery; choose appropriate AKS cluster-user/admin and/or Azure Kubernetes RBAC permissions for the required operation. | AKS-MCP Azure/AKS API calls otherwise return authorization failures. |
| Worker Kubernetes APIs | Authorize the identity presented to each worker API server. For Azure Kubernetes RBAC this is normally the UAMI principal (or a mapped Azure AD group); for a kubeconfig using another credential it is that credential's subject. | Kubernetes API authorization is independent of the management pod's token exchange. |
| Agent-to-tool | Give the agent an explicit tool allowlist through its MCP server reference. | A tool executes with AKS-MCP's permissions, not the agent pod's ServiceAccount permissions. |

The packaged chart creates a read-only `ClusterRole` and `ClusterRoleBinding`
by default. That binding governs the MCP's **management-cluster** Kubernetes
ServiceAccount; it does not grant access to worker APIs. It deliberately
excludes Secret reads unless `rbac.includeSecrets=true` is explicitly approved. See
[`chart/templates/rbac.yaml`](chart/templates/rbac.yaml).

### Central-MCP worker-cluster prerequisites

For every worker cluster, complete all of these independently of federation:

1. Assign the UAMI the least-privilege Azure role needed to discover/use that
   AKS cluster. Do not use a broad subscription role when a cluster or
   resource-group scope suffices.
2. Grant the identity presented to the worker Kubernetes API the required
   read-only Kubernetes authorization. With Azure Kubernetes RBAC this is an
   Azure RBAC assignment at the appropriate AKS scope; with native Kubernetes
   RBAC it is the appropriate `RoleBinding` or `ClusterRoleBinding` for the
   identity in the selected credential path.
3. Give AKS-MCP a deliberate worker-cluster connection path. The current chart
   can mount a kubeconfig Secret with `kubeconfig.enabled=true`, but federation
   alone neither creates that kubeconfig nor selects worker contexts.
4. Permit management-cluster-to-worker API connectivity: private DNS,
   routing/peering, firewall rules, and namespace egress `NetworkPolicy` must
   allow the target API endpoints.

No worker federation is necessary for any of the four steps unless a pod on
that worker itself must exchange a token for the UAMI.

## Configuration

Example Helm values, with public-safe placeholders:

```yaml
azure:
  tenantId: "{{AZURE_TENANT_ID}}"
  clientId: "{{UAMI_CLIENT_ID}}"
  subscriptionId: "{{AZURE_SUBSCRIPTION_ID}}"

workloadIdentity:
  enabled: true

app:
  accessLevel: readonly

rbac:
  create: true
  includeSecrets: false
```

Before deployment, verify that the target AKS cluster has OIDC issuer and
workload identity enabled, the workload-identity webhook is running, the
ServiceAccount subject matches the Azure federated credential, and the UAMI
has the necessary Azure role assignments. A pod restart is required after
changing the pod label, ServiceAccount annotation, or federated credential.

## Local validation

Render the chart without a cluster:

```bash
helm template aks-mcp ./chart \
  --namespace aks-mcp \
  --set workloadIdentity.enabled=true \
  --set-string azure.tenantId=AZURE_TENANT_ID \
  --set-string azure.clientId=UAMI_CLIENT_ID \
  --set-string azure.subscriptionId=AZURE_SUBSCRIPTION_ID \
  > /tmp/aks-mcp-rendered.yaml
```

Confirm the rendered deployment carries `azure.workload.identity/use: "true"`,
the ServiceAccount carries the UAMI client-ID annotation, and the rendered RBAC
matches the intended access level. Use server-side dry-run only against an
approved compatible cluster:

```bash
kubectl apply --dry-run=server -f /tmp/aks-mcp-rendered.yaml
```

### Evidence from the local chart build

The chart was rendered on 2026-07-22 with workload identity enabled and
placeholder-only values. The following checks passed:

| Check | Result |
|---|---|
| `helm lint platform/aks-mcp/chart` | 1 chart linted; 0 failed |
| `helm template` with workload identity enabled | Render succeeded |
| Rendered pod label | `azure.workload.identity/use: "true"` present |
| Rendered ServiceAccount annotation | `azure.workload.identity/client-id: "UAMI_CLIENT_ID"` present |
| Rendered authorization | `ClusterRoleBinding` present; default RBAC contains no Secret-read rule |
| `scripts/lint-yaml.sh --quiet` | 7 files checked; 0 failed |

This is an offline rendering check, not proof that a live cluster has its OIDC
issuer, webhook, federated credential, Azure role assignments, or remote API
connectivity configured.

## Quick start

```bash
helm upgrade --install aks-mcp ./chart \
  --namespace aks-mcp --create-namespace \
  -f chart/values.yaml
```

When specifying `toolNames` in `RemoteMCPServer`, list tools explicitly;
`None` causes a validation error.
