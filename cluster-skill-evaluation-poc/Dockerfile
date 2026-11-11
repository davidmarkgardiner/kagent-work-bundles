FROM python:3.12-slim@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
ARG TARGETARCH=amd64
RUN apt-get update && apt-get install -y --no-install-recommends bash curl jq ca-certificates && rm -rf /var/lib/apt/lists/* \
 && curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/v1.31.14/bin/linux/${TARGETARCH}/kubectl" \
 && curl -fsSLo /tmp/kubectl.sha256 "https://dl.k8s.io/release/v1.31.14/bin/linux/${TARGETARCH}/kubectl.sha256" \
 && cd /tmp && echo "$(cat kubectl.sha256)  kubectl" | sha256sum -c - \
 && install -m 0755 /tmp/kubectl /usr/local/bin/kubectl && rm /tmp/kubectl*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY contract.py eval_controller.py worker.py ./
COPY vendor ./vendor
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
ENTRYPOINT ["python", "/app/eval_controller.py"]
