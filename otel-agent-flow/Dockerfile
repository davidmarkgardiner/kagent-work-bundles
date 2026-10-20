FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
WORKDIR /app
COPY .build/grpcurl /usr/local/bin/grpcurl
COPY backend.py telemetry.py substrate_call.py workflow_demo.py /app/
COPY ui /app/ui
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BIND_ADDRESS=0.0.0.0
USER 10001:10001
EXPOSE 8787 8084
CMD ["python", "/app/backend.py"]
