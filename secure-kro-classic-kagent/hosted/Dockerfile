ARG PYTHON_BASE
ARG KUBECTL_IMAGE
FROM ${KUBECTL_IMAGE} AS kubectl
FROM ${PYTHON_BASE}
ARG KUBECTL_BINARY_PATH=/bin/kubectl
COPY --from=kubectl ${KUBECTL_BINARY_PATH} /usr/local/bin/kubectl
WORKDIR /app
COPY terminal_demo.py live_demo.py demo.py preflight.py query.py versions.lock.json live-onboarding.html ./
COPY runtime/golden.py ./runtime/golden.py
COPY demo/resource-notes.json ./demo/resource-notes.json
COPY examples/onboarding-payload.json ./examples/onboarding-payload.json
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
USER 65532:65532
EXPOSE 8766
ENTRYPOINT ["python3", "-B", "/app/live_demo.py"]
