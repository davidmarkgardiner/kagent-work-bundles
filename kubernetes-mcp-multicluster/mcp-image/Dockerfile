ARG KUBERNETES_MCP_BASE_IMAGE
FROM ${KUBERNETES_MCP_BASE_IMAGE}

# Supply the reviewed, pinned Linux kubelogin binary in the build context.
# The build is deliberately offline and preserves the upstream entrypoint.
COPY --chmod=0555 kubelogin /usr/local/bin/kubelogin
