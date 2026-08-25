# Sanitized derived-image home-lab receipt

Date: 2026-08-25

This receipt proves that the bundle's derived Kubernetes MCP image can carry
the pinned Azure `kubelogin` binary without changing the upstream server
runtime contract. It contains no kubeconfig, token, certificate, API address,
private host address, Authorization header, or Secret data.

## Inputs and build

- Kubernetes MCP base:
  `quay.io/containers/kubernetes_mcp_server:v0.0.66`
- Base registry digest:
  `sha256:6d650f4bd6ac303ad82713c997e73a2d001602f9bf17392c9b9a0e30e29c6423`
- Azure kubelogin release: `v0.2.19`
- Linux AMD64 archive digest:
  `sha256:ebaeff02aa899c5cae6a2b954b64fc02738185319df2570f7dc053451efa4b2f`
- Extracted binary digest:
  `sha256:d418d69189a56f9fcee1d7643507b37b4d1f846d2abcc6d920554a3ab8110a16`
- Derived OCI manifest:
  `sha256:c42e5e6022d66f7e0da3fddfc6f91b1dee5fc1940d473c1f3f66d9ca0137fb3f`
- Derived image config and node runtime image ID:
  `sha256:f43a5aa5a8bad6a863eec57c03b3c2361df4ac02554fedb6c70949a4630ca950`
- Target platform: `linux/amd64`

The official checksum file returned `OK`. The extracted helper was a
statically linked Linux AMD64 executable. The image was built from the
checked-in Dockerfile with `--pull=false` and build-network access disabled.
The build-time helper check reported the pinned tag and upstream Git hash.

The derived image preserved the upstream runtime contract:

```text
user:       65532:65532
entrypoint: /app/kubernetes-mcp-server
command:    --port 8080
helper:     /usr/local/bin/kubelogin
```

Both `kubelogin --version` and `kubelogin get-token --help` succeeded inside
the derived container.

## Live Kubernetes MCP proof

The image was transferred directly to the reachable AMD64 home-lab Kind node;
it was not published to an external registry. The existing Kubernetes MCP
Deployment was temporarily rolled to that exact local image.

A short-lived reader TokenRequest and a temporary single-context kubeconfig
Secret were used because the preceding multi-context home-lab proof tokens had
expired. The temporary context is called `management-proof` in this receipt.
The current home-lab bootstrap endpoint uses insecure TLS, so this temporary
credential is proof-only and does not satisfy the bundle's production TLS
gate.

Live results:

```text
KUBELOGIN_OK version=v0.2.19 platform=linux/amd64
MCP_PATH_OK path=direct tools=8 context=management-proof
MCP_PATH_OK path=agentgateway tools=8 context=management-proof
MCP_RESOURCE_READ_OK kind=Node expected-marker=true
```

The server exposed exactly the configured eight read-only tools. A
`resources_list` call selected the explicit context and returned its expected
node marker through both the direct Kubernetes MCP endpoint and agentgateway.
No tool response or raw marker is retained here.

## Cleanup and boundary

The test restored the original pinned image and original fleet kubeconfig
Secret, waited for the Deployment to become available, deleted the temporary
Secret, and removed the local token-bearing file. No proof credential remains
in the cluster.

This receipt proves:

- the exact Linux `kubelogin` release artifact is correctly packaged;
- the non-root MCP runtime can execute it;
- the derived layer does not break Kubernetes MCP tool discovery or reads; and
- agentgateway continues to route to the derived MCP server.

It does not prove an Azure Workload Identity token exchange, AKS API access,
the fleet discovery CronJob, or a fresh two-cluster crossover run. Those gates
require the work AKS environment. The earlier two-context home-lab receipt
still proves context isolation with the unmodified base image.
