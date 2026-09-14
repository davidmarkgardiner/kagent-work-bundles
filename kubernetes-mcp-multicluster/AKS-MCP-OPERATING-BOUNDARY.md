# AKS-MCP operating boundary

## Purpose

AKS-MCP is optional in this architecture. Retain it only for approved Azure
management-plane operations that Kubernetes MCP cannot perform, such as AKS
resource discovery, managed-cluster configuration, control-plane upgrades,
node-pool lifecycle, or Azure-side diagnostics.

AKS connectivity alone is not a reason to retain AKS-MCP. Kubernetes MCP can
connect to AKS clusters through the generated kubeconfig exactly as it connects
to the validated Kubernetes contexts in this bundle.

## Hard boundary

AKS-MCP must not be the routine workload-triage path when the requested action
is available through the Kubernetes API. It must not repeatedly merge
credentials into a shared writable kubeconfig inside its pod. Reuse its UAMI
for this bundle only while that identity remains compatible with the
read-only boundary. If AKS-MCP later receives Azure mutation permissions, give
the Kubernetes MCP pod a separate reader UAMI rather than sharing the broader
identity.

The morning credential CronJob reuses AKS-MCP's federated ServiceAccount and
UAMI to discover clusters only in its configured environment subscriptions
and obtain non-admin kubeconfig metadata. That does not require
exposing those Azure operations to the diagnostic Agent as MCP tools.

## When to deploy it

Deploy AKS-MCP only when all of these are true:

1. An explicit use case requires an Azure or AKS managed-service operation.
2. The exact AKS-MCP tools are allowlisted for a dedicated Agent or workflow.
3. Its Workload Identity has the minimum Azure role assignments at the
   smallest practical scope.
4. Kubernetes authorization is separately bounded for any cluster API calls.
5. Mutating operations have a human approval and auditable workflow boundary.

Otherwise, omit AKS-MCP and use the credential job plus Kubernetes MCP.

## Identity and federation

For a central management-cluster deployment, Azure federation follows the OIDC
issuer and ServiceAccount of the cluster running the AKS-MCP or credential-job
pod. It does not follow the destination AKS cluster. Destination authorization
remains a separate Azure RBAC and Kubernetes RBAC decision.

The refresh Job can reuse the existing AKS-MCP federated subject because it
runs as that exact ServiceAccount. The Kubernetes MCP pod uses a different
ServiceAccount and therefore needs a second federated credential on the same
UAMI for its exact subject. Sharing the UAMI does not make federation subjects
interchangeable.

Do not use cluster-admin kubeconfigs, owner-level subscription roles, shared
static client secrets, or an Azure identity that can mutate every subscription
merely because the fleet spans multiple subscriptions.

## Coexistence rule

When both tools are retained, expose them as separate `RemoteMCPServer`
objects, separate tool allowlists and normally separate Agents:

- Kubernetes MCP: routine read-only Kubernetes evidence.
- AKS-MCP: narrowly approved Azure management-plane action.

The Kubernetes Agent may recommend escalation but must not silently call the
AKS-MCP mutation path.
