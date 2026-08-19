# Shared password/UAMI FastMCP image. Refresh this base deliberately in approved CI.
FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 fastmcp \
    && useradd --uid 10001 --gid fastmcp --create-home --home-dir /app --shell /usr/sbin/nologin fastmcp

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY verify_live.py .
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "/app/server.py"]
