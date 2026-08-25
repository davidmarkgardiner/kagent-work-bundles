ARG KUBERNETES_MCP_BASE_IMAGE=invalid.invalid/base-image-must-be-supplied:invalid
FROM ${KUBERNETES_MCP_BASE_IMAGE}

ARG KUBELOGIN_VERSION

# Supply the reviewed, pinned Linux kubelogin binary in the build context.
# The build is deliberately offline and preserves the upstream entrypoint.
COPY --chmod=0555 kubelogin /usr/local/bin/kubelogin

# Fail the image build when the supplied binary has the wrong architecture or
# cannot execute in the upstream runtime image.
RUN /usr/local/bin/kubelogin --version

LABEL org.opencontainers.image.title="Kubernetes MCP server with Azure kubelogin" \
      org.opencontainers.image.description="Offline-derived Kubernetes MCP image for AKS exec-plugin authentication" \
      org.opencontainers.image.version="${KUBELOGIN_VERSION}"
