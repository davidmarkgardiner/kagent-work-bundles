# Sanitized live home-lab receipt

Date: 2026-08-24

This receipt contains no kubeconfig, token, certificate, API address, private
hostname, node name, internal cluster name, Authorization header, or Secret
data. Runtime aliases are redacted below as `management-proof` and
`worker-proof`.

## Build and deployment

- Public image tag: `quay.io/containers/kubernetes_mcp_server:latest`
- Published chart: `oci://ghcr.io/containers/charts/kubernetes-mcp-server`
- Helm release: `kubernetes-mcp-fleet`
- Namespace: `kubernetes-mcp-poc`
- Deployment: Ready `1/1`; service-account token automount disabled
- Credential object: content-hashed and immutable
- Approved context count: two
- Exposed tools: `events_list`, `namespaces_list`, `pods_get`,
  `pods_list`, `pods_list_in_namespace`, `pods_log`, `resources_get`,
  `resources_list`

The running pod resolved to the expected image artifact. The proof used one
replica because the management node had limited spare requested capacity.

## Authorization and network boundary

- The dedicated reader identities authenticated successfully in both targets.
- Positive namespace, node, pod, event, workload, job, and pod-log reads passed.
- Secret, ServiceAccount, RBAC, mutation, pod-exec, and token-creation checks
  were denied in both targets.
- Namespace default-deny and the MCP caller allow policy were present.
- An unrelated, unlabelled test pod timed out when connecting to the MCP
  Service and was deleted immediately after the check.
- A pre-existing unrelated MCP Deployment retained its identity and generation.

## MCP, agentgateway, and kagent

- Direct MCP: eight exact tools, two contexts, zero crossover.
- Agentgateway MCP: eight exact tools, two contexts, zero crossover.
- Agentgateway alternating test: 20 requests, zero crossover.
- Direct `RemoteMCPServer`: accepted.
- Gateway `RemoteMCPServer`: accepted.
- `AgentgatewayBackend`: accepted.
- `HTTPRoute`: accepted.
- `kubernetes-mcp-fleet-agent`: Accepted and Ready.

The repository A2A helper invoked the gateway-backed Agent twice. Sanitized
responses were:

```text
Context: worker-proof
Node count: 3

Context: management-proof
Node count: 1
```

These calls proved:

```text
kagent Agent -> kagent RemoteMCPServer -> agentgateway -> Kubernetes MCP
             -> selected kubeconfig context -> target Kubernetes API
```

## Boundary of this receipt

This proves the home-lab multi-context data-plane path. It does not claim an
AKS cluster test or prove the Azure Workload Identity/`kubelogin` refresh
job. Validate that path against a real AKS target before production use.
