# AKS bootstrap registry authorization

Source: https://learn.microsoft.com/en-us/troubleshoot/azure/azure-kubernetes/error-codes/vmextensionerror-oraspullunauthorized
Reviewed: 2026-10-21

Demo evidence code: AKS-KB-ORAS-212-R1

This demo runbook summarizes Microsoft's guidance. It is not an incident report.

For network-isolated AKS provisioning, OrasPullUnauthorizedVMExtensionError with vmssCSE exit 212 can indicate that the kubelet identity cannot authenticate to the private bootstrap ACR cache.

Inspect the provisioning log before choosing a response. Distinguish a registry HTTP 401, an identity-not-found HTTP 400, and an IMDS timeout. Confirm the bootstrap registry and the kubelet identity attached to the node.

For registry authorization, check the registry's permissions mode. ABAC-enabled registries use Container Registry Repository Reader. Registries using ordinary RBAC use AcrPull. Missing identity attachment and IMDS failures need separate investigation.

These are proposed checks. Obtain approval through the platform's remediation process before changing role assignments, identity bindings, or reconciling a real cluster. This demo executes no Azure commands.
