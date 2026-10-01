FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY server.py store.py ./
ENV GUIDANCE_HOST=0.0.0.0 GUIDANCE_PORT=9290 PYTHONDONTWRITEBYTECODE=1
USER 65532:65532
EXPOSE 9290
CMD ["python", "server.py"]
