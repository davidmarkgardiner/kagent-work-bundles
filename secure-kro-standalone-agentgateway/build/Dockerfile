# One fixed image for agent | facade | golden. Standard-library Python only: no pip, no package manager,
# no downloads. PYTHON_BASE must be the preloaded approved base pinned by build.py:
#   ...@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
COPY app /app
COPY content /app/content
# Build-time integrity check of the reviewed content against its recipe (runs offline).
RUN ["python3", "-B", "-E", "-s", "/app/main.py", "selftest"]
USER 65532:65532
WORKDIR /app
ENTRYPOINT ["python3", "-B", "-E", "-s", "/app/main.py"]
