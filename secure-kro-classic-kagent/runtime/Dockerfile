ARG PYTHON_BASE
FROM ${PYTHON_BASE}
COPY golden.py /app/golden.py
USER 65532:65532
ENTRYPOINT ["python3", "-B", "/app/golden.py", "--config", "/golden/config.json"]
