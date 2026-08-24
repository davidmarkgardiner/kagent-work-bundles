# Air-gapped Kubernetes MCP image for AKS

AKS kubeconfigs created with `--format exec` and converted with
`kubelogin -l workloadidentity` execute `kubelogin` when the MCP calls a target
API. The upstream `v0.0.66` image does not include that helper, so build a thin
derived image without downloading anything during the build:

```bash
docker build \
  --build-arg KUBERNETES_MCP_BASE_IMAGE={{INTERNAL_REGISTRY}}/{{MIRROR}}/kubernetes_mcp_server:v0.0.66 \
  --tag {{INTERNAL_REGISTRY}}/{{PROJECT}}/kubernetes_mcp_server:v0.0.66-kubelogin-{{VERSION}} \
  mcp-image
```

Place the approved, pinned Linux `kubelogin` binary next to the Dockerfile.
Record both the upstream base-image digest and helper digest in the work
change. Put the derived image repository and tag in `work-values.env` as
`IMAGE_REGISTRY`, `IMAGE_REPOSITORY`, and `IMAGE_VERSION`.
