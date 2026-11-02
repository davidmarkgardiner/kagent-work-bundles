# Build the application from repository source

Download the repository from GitHub and use the `otel-agent-flow` folder. No separate source ZIP or prebuilt Docker archive is required. Build the application image through the work environment's normal CI or internal build service.

The browser code is HTML, CSS, and JavaScript. The same application also has a Python backend that receives OTLP, correlates traces and actor events, invokes the selected agent through gRPC, and serves the UI. Kubernetes runs that backend in a Linux container on Linux nodes. The image packages its Python runtime, static UI, and checksum-verified grpcurl client. It does not require a separate Linux VM or a Linux laptop.

`image-lock.json` records the upstream digests and the earlier local rehearsal image. Its application image ID/archive hash is historical evidence, not a requirement to import that archive or a digest for the latest source. Build this revision and record its resulting internal registry digest.

```bash
export FLOW_IMAGE='{{INTERNAL_REGISTRY}}/otel-agent-flow:{{REVIEWED_TAG}}'
export TARGETARCH=amd64
bash scripts/build-image.sh
```

The script builds locally and does not push. An internal CI runner can run the same build. Publish through the approved registry process and set `image.repository` and `image.digest` in private operator values. The digest takes precedence over the tag. A Docker image ID is not a registry manifest digest.

Existing-agent mode needs the application and collector images. It reuses the installed agentgateway, model route, agent runtime, and MCP servers. Bundled mode also needs the gateway and digest-pinned Go ADK images. Mirror only the components selected by the profile. The Caddy image is for local HTTPS rehearsal and is not deployed by either AKS Istio profile.

For a disconnected build, provide the pinned Python base and the verified grpcurl archive through the approved internal artifact process. Place `grpcurl-1.9.3-amd64.tar.gz` or `grpcurl-1.9.3-arm64.tar.gz` in `.build/`. The script validates its SHA-256 before extraction. Registry credentials, populated work values, certificate keys, and rollback state stay outside the repository.
