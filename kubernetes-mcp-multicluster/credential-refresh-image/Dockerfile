ARG AZURE_CLI_IMAGE
FROM ${AZURE_CLI_IMAGE}

# Supply reviewed, pinned Linux binaries in the build context. The build is
# deliberately offline: it performs no curl, package-manager, or Git fetch.
COPY kubectl kubelogin jq /usr/local/bin/
RUN chmod 0555 /usr/local/bin/kubectl /usr/local/bin/kubelogin /usr/local/bin/jq \
    && bash -c 'declare -A check=(); mapfile -t check_values < /dev/null' \
    && bash -c 'for command_name in awk date grep mktemp rm sed seq sha256sum sort tr wc; do command -v "$command_name" >/dev/null || exit 1; done' \
    && az version >/dev/null \
    && kubectl version --client=true >/dev/null \
    && kubelogin --version >/dev/null \
    && jq --version >/dev/null

USER 10001:10001
WORKDIR /work
