ARG PYTHON_BASE
FROM ${PYTHON_BASE}
WORKDIR /app
COPY server.py /app/server.py
USER 65532:65532
ENTRYPOINT ["python3", "/app/server.py", "--config", "/config/runtime.json"]
