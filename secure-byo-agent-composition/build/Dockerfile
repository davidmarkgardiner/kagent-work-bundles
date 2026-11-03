ARG PYTHON_BASE
FROM ${PYTHON_BASE}
ARG KAGENT_SHA256
COPY kagent /usr/local/bin/kagent
RUN test -n "$KAGENT_SHA256" && echo "$KAGENT_SHA256  /usr/local/bin/kagent" | sha256sum -c -
COPY runtime/server.py /app/runtime/server.py
COPY composition /app/composition
USER 65532:65532
WORKDIR /app
ENTRYPOINT ["python3", "/app/runtime/server.py", "--config", "/config/runtime.json"]
