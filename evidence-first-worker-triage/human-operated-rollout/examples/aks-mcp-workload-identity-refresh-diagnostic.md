# AKS-MCP Workload Identity: Refresh Diagnostic

This is the check to give the work agent when it reports that an AKS-MCP token
must be manually refreshed every hour. **UAM below means UAMI** (user-assigned
managed identity).

## TL;DR

Manual hourly token refresh should not be part of the intended
workload-identity operating model. A projected Kubernetes ServiceAccount token
is rotated by Kubernetes, and an Azure SDK workload-identity credential can
obtain renewed Azure access tokens as required. An Azure access token lifetime
near one hour can be normal.

However, this is not purely a configuration question. The current upstream
AKS-MCP `main` implementation (checked at `8e84bce`, 2026-07-17) has **two
different paths**:

- ARM-backed components create `azidentity.DefaultAzureCredential`, which can
  use workload identity normally.
- The Azure CLI/kubectl path reads `AZURE_FEDERATED_TOKEN_FILE` once and runs
  `az login --service-principal --federated-token ...` during server startup.
  The server does not contain a periodic re-login/refresh loop.

That startup-only Azure CLI path is a credible explanation for a failure at an
access-token boundary. It must be tested separately from the ARM SDK path.

Do not paste, cache, or manually renew a token. Instead, prove the identity
chain below and identify whether the failure is federation, Azure/Kubernetes
authorization, pod injection, or the upstream Azure CLI startup-login path.

```text
AKS-MCP pod
  -> projected ServiceAccount token (automatically rotated)
  -> Microsoft Entra federated credential
  -> UAMI access token (automatically reacquired by the Azure credential)
  -> Azure/AKS and worker-cluster read authorization
```

## Topology rule first

Federate the OIDC issuer of the cluster **hosting the AKS-MCP pod**, not every
cluster that the MCP server investigates.

| Deployment model | Required federated credential issuer | UAMI still needs access to |
|---|---|---|
| Central MCP | Management-cluster OIDC issuer | Each approved worker AKS resource and its Kubernetes API authorization path |
| Per-worker MCP | That worker cluster's OIDC issuer | Its local worker cluster (and any explicitly approved remote target) |

For the planned central management-cluster AKS-MCP, a missing worker-cluster
federation is normally **not** the reason the management pod cannot refresh a
UAMI token. A worker-cluster access failure after a successful exchange is
usually authorization, target context, or network connectivity instead.

## Variables

Create a local, non-committed values file. Do not put values or tokens in this
document, a ticket, or shell history.

```bash
export MANAGEMENT_CONTEXT='{{MANAGEMENT_KUBECTL_CONTEXT}}'
export AKS_MCP_NAMESPACE='{{AKS_MCP_NAMESPACE}}'
export AKS_MCP_DEPLOYMENT='{{AKS_MCP_DEPLOYMENT}}'
export AKS_MCP_SERVICE_ACCOUNT='{{AKS_MCP_SERVICE_ACCOUNT}}'
export AKS_MCP_LABEL='app.kubernetes.io/name=aks-mcp'
export UAMI_RESOURCE_GROUP='{{UAMI_RESOURCE_GROUP}}'
export UAMI_NAME='{{AKS_MCP_UAMI_NAME}}'
export MANAGEMENT_AKS_RESOURCE_GROUP='{{MANAGEMENT_AKS_RESOURCE_GROUP}}'
export MANAGEMENT_AKS_NAME='{{MANAGEMENT_AKS_NAME}}'
```

## Gate 1 — establish the exact failure

Record the timestamp and a **safe error category**, not a bearer token or full
authorization header. Check whether it starts only after about an hour, and
whether a pod restart merely disguises the fault.

```bash
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" \
  logs deploy/"$AKS_MCP_DEPLOYMENT" --since=3h \
  | rg -i 'workload.?identity|credential|federat|token|azure|entra|unauthori[sz]ed|forbidden|expired'
```

Interpret before changing configuration:

| Evidence | Likely boundary |
|---|---|
| `AADSTS70021`, no matching federated identity, issuer/subject/audience mismatch | Federation tuple |
| Credential unavailable or missing `AZURE_FEDERATED_TOKEN_FILE` | Pod admission/injection |
| Token exchange succeeds, but worker action is `403`/Forbidden | Azure RBAC, worker Kubernetes RBAC, or target-cluster selection |
| ARM SDK path remains healthy, but `call_kubectl`/Azure CLI path fails after expiry | Current upstream startup-only Azure CLI federated login is a likely cause |
| All paths fail after expiry and restart cures it | Inspect the mounted identity inputs and the image/version before treating this as a pure RBAC issue |

## Gate 2 — prove the UAMI exists and is the expected identity

```bash
az identity show \
  --resource-group "$UAMI_RESOURCE_GROUP" \
  --name "$UAMI_NAME" \
  --query '{id:id,clientId:clientId,principalId:principalId,tenantId:tenantId}' \
  --output json
```

Compare the returned `clientId` with the AKS-MCP ServiceAccount annotation;
the `principalId` is commonly what Azure role assignments reference.

```bash
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" \
  get serviceaccount "$AKS_MCP_SERVICE_ACCOUNT" -o yaml
```

Required annotation:

```yaml
metadata:
  annotations:
    azure.workload.identity/client-id: {{UAMI_CLIENT_ID}}
```

For the repository chart, `workloadIdentity.enabled=true` requires both
`azure.clientId` and `azure.tenantId`; it renders the annotation above.

## Gate 3 — prove Azure role assignments separately from federation

Federation establishes who the pod can become. It does not authorise calls.
List the UAMI's Azure assignments and compare their scopes with the approved
management/worker AKS resources:

```bash
UAMI_PRINCIPAL_ID="$(az identity show --resource-group "$UAMI_RESOURCE_GROUP" --name "$UAMI_NAME" --query principalId --output tsv)"
az role assignment list --assignee "$UAMI_PRINCIPAL_ID" --all --output table
```

Then check the worker-cluster Kubernetes authorization path independently. For
Azure Kubernetes RBAC, inspect the relevant Azure role at the AKS scope; for a
kubeconfig-based path, inspect the identity represented by that kubeconfig.
Do not assume the central AKS-MCP ServiceAccount's local ClusterRoleBinding
grants worker-cluster access.

## Gate 4 — prove the federated credential tuple

Read the issuer of the cluster that hosts AKS-MCP:

```bash
MANAGEMENT_ISSUER="$(az aks show \
  --resource-group "$MANAGEMENT_AKS_RESOURCE_GROUP" \
  --name "$MANAGEMENT_AKS_NAME" \
  --query oidcIssuerProfile.issuerUrl --output tsv)"
printf '%s\n' "$MANAGEMENT_ISSUER"

az identity federated-credential list \
  --resource-group "$UAMI_RESOURCE_GROUP" \
  --identity-name "$UAMI_NAME" \
  --output json
```

There must be one matching tuple:

```text
issuer:   $MANAGEMENT_ISSUER
subject:  system:serviceaccount:$AKS_MCP_NAMESPACE:$AKS_MCP_SERVICE_ACCOUNT
audience: api://AzureADTokenExchange
UAMI:     $UAMI_NAME
```

Match the issuer exactly, including its trailing slash behaviour. Do not
compare a worker issuer when AKS-MCP is deployed centrally. If using ASO,
also verify the `FederatedIdentityCredential` resource is Ready and its source
ConfigMap contains the same management issuer.

## Gate 5 — prove workload-identity injection into a newly created pod

The AKS workload-identity webhook acts at pod admission. A label/annotation
fix does not retrofit a running pod; restart the AKS-MCP Deployment only after
recording the current state and only through the approved change process.

```bash
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" \
  get deploy "$AKS_MCP_DEPLOYMENT" -o yaml
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" \
  get pods -l "$AKS_MCP_LABEL" -o yaml
```

Required pod-template label:

```yaml
spec:
  template:
    metadata:
      labels:
        azure.workload.identity/use: "true"
```

On a newly admitted AKS-MCP pod, check the injected environment and projected
file **without printing its contents**:

```bash
AKS_MCP_POD="$(kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" get pods -l "$AKS_MCP_LABEL" -o jsonpath='{.items[0].metadata.name}')"
kubectl --context "$MANAGEMENT_CONTEXT" -n "$AKS_MCP_NAMESPACE" exec "$AKS_MCP_POD" -- sh -c '
  env | grep "^AZURE_" | sed -E "s/(=.*)/=<redacted>/"
  test -n "${AZURE_FEDERATED_TOKEN_FILE:-}" && test -r "$AZURE_FEDERATED_TOKEN_FILE"
'
```

Expected injected identity inputs include `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`
and `AZURE_FEDERATED_TOKEN_FILE`; the final `test` must succeed. Never run
`cat "$AZURE_FEDERATED_TOKEN_FILE"`.

## Gate 6 — verify the refresh behaviour safely

Use two read-only calls separated by more than one hour, with the same approved
target and correlation marker. Deliberately cover both paths where they are
enabled:

1. One ARM-backed AKS-MCP component that uses the Azure SDK credential.
2. One `call_kubectl` or other Azure CLI-backed operation used by the triage
   workflow.

Capture safe logs/telemetry for both. Pass when both calls succeed without a
manual token update, a copied token, or a pod restart. If the first succeeds
and the second fails:

1. Preserve the safe error category and timestamps.
2. Re-run Gates 2–5; do not renew a token by hand.
3. Record whether the failing operation is ARM SDK-backed or Azure CLI/kubectl
   backed. Do not report the two paths as equivalent.
4. For an Azure CLI/kubectl-only failure, capture the AKS-MCP image digest and
   upstream version/commit. The currently inspected upstream source logs in
   once at startup and has no periodic federated re-login loop; open or link a
   targeted upstream issue rather than adding a manual refresh job.
5. Check that no local startup wrapper copies `AZURE_FEDERATED_TOKEN_FILE` into
   a static file or caches a raw Azure access token.
6. Escalate with the redacted pod spec, ServiceAccount annotation, FIC tuple,
   role-assignment scope and both error windows.

## Copy/paste instruction for the work agent

> Diagnose AKS-MCP workload identity without manually refreshing or printing
> any token. First identify whether AKS-MCP is central (management cluster) or
> per-worker, then validate the UAMI, Azure role assignments, exact FIC issuer
> + subject + audience tuple, ServiceAccount annotation, pod-template label,
> injected `AZURE_*` environment and readable projected token-file path.
> Treat worker-cluster access as a separate Azure/Kubernetes RBAC and network
> check. Prove two read-only calls more than one hour apart. Report only safe
> error categories and redacted configuration evidence. If the second call
> fails, identify whether the failing operation is ARM SDK or Azure CLI/kubectl
> backed. The current upstream AKS-MCP Azure CLI login is startup-only, so do
> not hide that defect with a manual refresh job, a copied token, or a routine
> pod restart. Capture the image digest/version and raise the exact boundary.

## References

- [AKS-MCP workload identity model](../../../../platform/aks-mcp/README.md)
- [Repository workload identity federation pattern](../../../../infra/workload-identity/README.md)
- [AKS Workload Identity overview](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview)
- [Upstream AKS-MCP startup Azure CLI login](https://github.com/Azure/aks-mcp/blob/8e84bcee1532c8019951469de9d7e04f6a0d3b53/internal/azcli/login.go)
- [Upstream AKS-MCP Azure SDK credential client](https://github.com/Azure/aks-mcp/blob/8e84bcee1532c8019951469de9d7e04f6a0d3b53/internal/azureclient/client.go)
