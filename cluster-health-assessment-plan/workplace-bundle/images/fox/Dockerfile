ARG GO_BUILDER_IMAGE
ARG RUNTIME_IMAGE
FROM ${GO_BUILDER_IMAGE} AS build

WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go test ./... && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/autonomous-monitor .

FROM ${RUNTIME_IMAGE}
LABEL org.opencontainers.image.title="autonomous-monitor-state-only" \
      org.opencontainers.image.description="Locally adapted Fox namespace monitor with per-finding publication disabled" \
      org.opencontainers.image.source="https://github.com/foxj77/autonomous-monitor"
COPY --from=build --chown=65532:65532 /out/autonomous-monitor /autonomous-monitor
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/autonomous-monitor"]
