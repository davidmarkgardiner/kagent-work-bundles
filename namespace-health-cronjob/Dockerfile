FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
ARG TARGETARCH
COPY wheelhouse/${TARGETARCH}/ /wheelhouse/
COPY requirements.lock /requirements.lock
RUN python -m pip install --no-index --find-links=/wheelhouse --require-hashes --no-cache-dir -r /requirements.lock \
    && rm -rf /wheelhouse
WORKDIR /app
COPY src/ /app/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
CMD ["python","/app/publish.py"]
