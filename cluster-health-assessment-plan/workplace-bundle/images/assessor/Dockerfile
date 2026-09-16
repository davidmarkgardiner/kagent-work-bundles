ARG PYTHON_BASE_IMAGE=python:3.11-slim@sha256:d1053354624536b044162aaab1e418bd000ea35184fb1ae098ab3166b1072e72
FROM ${PYTHON_BASE_IMAGE}

LABEL org.opencontainers.image.title="cluster-health-assessor" \
      org.opencontainers.image.description="Deterministic Kubernetes health assessment and threshold-alert controller" \
      org.opencontainers.image.source="local-work-bundle"

WORKDIR /app
COPY b1/collector.py b1/health.py b1/metrics.py /app/
COPY workplace-bundle/runtime/alert_controller.py workplace-bundle/runtime/gitlab_summary_writer.py /app/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 65532:65532
ENTRYPOINT ["python3", "/app/alert_controller.py"]
