# Build and scan this image in the organisation's trusted CI, then mirror it
# into the office registry. Do not install packages at Pod startup in production.
FROM python:3.12-slim@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check --target /opt/data-mcp \
      -r requirements.txt
COPY server.py .
ENV PYTHONPATH=/opt/data-mcp
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "/app/server.py"]
