# Eval runner image: python + PyYAML + kubectl. Build once, mirror internally,
# reference by digest as EVAL_IMAGE in .gitlab-ci.yml.
FROM python:3.12-slim
ARG KUBECTL_VERSION=v1.31.4
ARG TARGETARCH=amd64
ADD https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl /usr/local/bin/kubectl
RUN chmod 0755 /usr/local/bin/kubectl && useradd -u 10001 -m eval
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
USER 10001
