# Sanitized live home-lab receipt

Date: 2026-08-24

This receipt contains no kubeconfig, token, certificate, API address, private
hostname, node name, internal cluster name, Authorization header, or Secret
data. Runtime aliases are redacted below as `management-proof` and
`worker-proof`.

## Build and deployment

- Original home-lab-only image input: mutable, unpinned `latest`; this is not
  the shipped `v0.0.66` coordinate.
- Chart: local `charts/kubernetes-mcp-server` directory, version `0.1.0`
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
- The original direct `RemoteMCPServer` was accepted during discovery proof,
  then removed. The final kagent state contains only the gateway registration.
- Gateway `RemoteMCPServer`: accepted.
- `AgentgatewayBackend`: accepted.
- `HTTPRoute`: accepted.
- `kubernetes-mcp-fleet-agent`: Accepted and Ready.
- The air-gap bundle re-verification rendered its non-Helm resources with
  Kustomize, applied them with `kubectl apply -k`, and repeated the complete
  direct/gateway 20-request smoke successfully. The revised smoke uses direct
  MCP JSON-RPC over `curl`; it does not download an npm inspector package.
- The release-matched `v0.0.66` image tag was confirmed in both official
  registries, and the local `v0.0.66` source chart rendered that tag correctly.
  The running pod receipt above remains the separately pinned image artifact
  used for the live behavior proof.
- The corrected crossover assertion uses `any(...)` across every MCP content
  entry. A multi-entry fixture proved both positive and negative marker cases,
  followed by the live direct/gateway two-context and 20-request gateway smoke.
- Final ingress admits only agentgateway; target API egress is restricted to
  configured private CIDRs. The first live attempt exposed a missing target
  CIDR and failed closed until that CIDR was added.
- A real TokenRequest on the CA-backed target returned 86,400 seconds and
  passed the configured 82,800-second minimum. Full bundle refresh correctly
  refused the separate bootstrap context that currently uses insecure TLS, so
  no new combined Secret was published or activated during this remediation.
- The live namespace contained one active bundle credential revision and no
  inactive revisions to prune. The active revision is now ownership-labelled
  and annotated with its earliest JWT expiry; future successful deployments
  prune every inactive labelled revision automatically.

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
