# OTel agent flow: registry import and build handoff sheet

Checked 27 October 2026. Default scope: reuse the existing approved agent, model route, agentgateway and MCP servers with `integration.mode: existing`.

## 1. Container image inventory

Import the three **Required** rows for the existing-agent deployment and its source build. Include conditional rows only for the stated profile. Registry hosts and repository paths are separate below; Docker Hub official images include `library/`.

| Priority | Purpose | Source registry | Repository path | Upstream tag |
|---|---|---|---|---|
| Required | Build base | `docker.io` | `library/python` | 3.12-slim-bookworm |
| Required | Go build stage, every profile | `docker.io` | `library/golang` | 1.27-bookworm |
| Required | Demo collector runtime | `docker.io` | `otel/opentelemetry-collector` | 0.146.0 |
| Conditional | Bundled profiles only | `cr.agentgateway.dev` | `agentgateway` | v1.5.0 |
| Conditional | Bundled substrate or both only | `ghcr.io` | `kagent-dev/kagent/golang-adk` | No tag recorded; use digest |
| Conditional | Bundled live Kubernetes MCP only | `ghcr.io` | `kagent-dev/kagent/tools` | 0.3.0 |
| Local only | Local HTTPS rehearsal; omit for AKS Istio | `docker.io` | `library/caddy` | 2.10.2-alpine |

### Exact import references

Use these complete digest-pinned references in the import request. The tags above are the bundle's recorded tags; import by digest to select the exact reviewed content.

**Build base**

```text
docker.io/library/python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
```

**Go build stage, every profile**

```text
docker.io/library/golang:1.27-bookworm@sha256:5c3e9b43cfd3bb95c7937462e29d87ada57b481a96fa23ad0eb61778d7a00110
```

**Demo collector runtime**

```text
docker.io/otel/opentelemetry-collector:0.146.0@sha256:60cf8cfda7086e792450a746953d5ec9579e440ae0d8a1e16608bb9960699844
```

**Bundled profiles only**

```text
cr.agentgateway.dev/agentgateway:v1.5.0@sha256:bf2f339ef326d32def2aaeb44b1b4549801293c19b89e764a4228667d97d9896
```

**Bundled substrate or both only**

```text
ghcr.io/kagent-dev/kagent/golang-adk@sha256:10ef1350786b5d21bc002ed54833fd0272ea7cd8182a92977686b7bafa7f67d3
```

**Bundled live Kubernetes MCP only**

```text
ghcr.io/kagent-dev/kagent/tools:0.3.0@sha256:cb89eb76216195a90cac73846b447525b6e6e33e45154d1ded9621bf11340315
```

**Local HTTPS rehearsal; omit for AKS Istio**

```text
docker.io/library/caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d
```

The Go ADK image has no named upstream tag in the bundle. Its digest is the exact identifier. The kagent Helm version below must not be substituted as an assumed image tag.

Verification performed: all seven digest references returned upstream manifests, the returned manifest bytes hashed to the requested digests, and each index includes Linux amd64 and arm64. Image layers were not downloaded and no internal import was performed. The checks address pinned digests, not whether mutable tags still point to them.

For Docker Hub, `docker.io` is the image-reference host and `registry-1.docker.io` is its registry API host. Registry authentication and layer transfers may use additional endpoints. These hosts identify the import sources; this is not a complete firewall allowlist.

The import receipt must record source reference, selected architecture, full internal reference, and internal manifest digest. Preserve the multi-platform index where supported. If the import process copies only one platform or changes the manifest, record its resulting internal digest and use that digest in deployment values.

## 2. Non-container prerequisites for a disconnected source build

| Input | Exact version or pin | Source / handling |
|---|---|---|
| Application source | Freeze the selected `kagent-work-bundles` commit before building | https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/otel-agent-flow |
| kagent upstream source | `b8d8b5ca7dd2cc4fba9ab1cc5c2b4b40536d0bf2` | https://github.com/kagent-dev/kagent.git ; make the full pinned source available to CI |
| Go modules | Complete module graph locked by that source's `go/go.mod` and `go/go.sum`, including replacements | Provide an approved internal module proxy/cache or reviewed vendored build. Default Go resolution may contact public module/checksum services and VCS hosts. Image imports alone do not supply these modules. |
| grpcurl Linux amd64 | `1.9.3` | https://github.com/fullstorydev/grpcurl/releases/download/v1.9.3/grpcurl_1.9.3_linux_x86_64.tar.gz |
| grpcurl Linux arm64 | `1.9.3`; alternative to amd64 | https://github.com/fullstorydev/grpcurl/releases/download/v1.9.3/grpcurl_1.9.3_linux_arm64.tar.gz |
| Operator Python dependency | `PyYAML==6.0.3` | Supply through the approved internal Python package repository or a compatible offline wheel. This is for operator scripts, not a Dockerfile pip install. |
| Operator/build tools | Existing approved toolchain | Docker/BuildKit on the builder; Python 3, bash, curl, tar; Helm 3, kubectl and OpenSSL as used by the selected operator scripts |

grpcurl archive SHA-256 values:

```text
linux/amd64  a926b62a85787ccf73ef8736b3ae554f1242e39d92bb8767a79d6dd23b11d1d5
linux/arm64  b20a00c1cb82ab81ec32696766d4076e99b4cb5ca0823a71767ba64dbea0f263
```

Put the selected archive in the bundle as `.build/grpcurl-1.9.3-amd64.tar.gz` or `.build/grpcurl-1.9.3-arm64.tar.gz`. The build script validates its checksum and extracts the executable.

The stock Dockerfile always compiles the standalone Go binary, including for existing-agent mode. It uses public image references, a hardcoded GitHub fetch and `go mod download`. The build agent must update source/base-image resolution and module access to the approved internal mirrors. Merely importing the container images does not make this Dockerfile fully offline.

## 3. Conditional OCI Helm charts

These are platform chart artifacts, not application container images. Existing-agent mode uses the bundled local demo chart and leaves the platform releases unchanged, so it does not need to fetch these charts. Bundled Substrate telemetry reconciliation may need them.

| Source registry | OCI chart repository | Chart version | Internal override |
|---|---|---|---|
| `ghcr.io` | `oci://ghcr.io/kagent-dev/kagent/helm/kagent` | `1.0.0-alpha8` | `FLOW_KAGENT_CHART` |
| `ghcr.io` | `oci://ghcr.io/kagent-dev/substrate/helm/substrate` | `0.4.0-alpha1` | `FLOW_SUBSTRATE_CHART` |

Chart locations and versions are read from the bundle; their upstream artifacts were not fetched in this check. This sheet does not inventory every controller, database, object-store or worker runtime artifact needed to bootstrap Substrate. The existing-agent profile assumes an already healthy, approved platform. No new platform installation or upgrade is implied.

## 4. Application image to build after imports

The final application image is built from this bundle. It has no published upstream registry image to import for the current source. Historical `poc-*` Docker image IDs in `image-lock.json` are rehearsal evidence.

```text
Output registry:   {{INTERNAL_REGISTRY}}
Output repository: {{TEAM_PATH}}/otel-agent-flow
Output tag:        {{REVIEWED_TAG_OR_SOURCE_COMMIT}}
Output platform:   linux/{{TARGETARCH}}
Deploy reference:  {{INTERNAL_REGISTRY}}/{{TEAM_PATH}}/otel-agent-flow@sha256:{{NEW_REGISTRY_MANIFEST_DIGEST}}
```

Build through the approved internal pipeline. `scripts/build-image.sh` accepts `FLOW_IMAGE` and `TARGETARCH`, builds locally and does not push. Publish through the approved registry process and record the registry manifest digest, rather than a local Docker image ID.

## 5. Work variables and deployment gates

After imports and a successful application build, fill private operator values with the following:

| Variable / setting | Required input |
|---|---|
| `image.repository`, `image.digest` | Newly published application repository and internal registry manifest digest |
| `collectorImage` | Imported collector reference, pinned to its internal digest |
| `imagePullSecrets` / node registry access | Approved internal registry pull access |
| `integration.mode` | `existing` for the initial scope |
| `integration.existingAgent`, `agentNamespace`, `workerPool` | Existing Ready read-only Substrate agent and approved ready worker pool |
| `integration.controllerAddress` | Existing controller gRPC address if it differs from the chart default |
| `collector.sourceNamespaces` | Actual gateway and MCP namespaces where applicable |
| Istio Gateway, hostname, TLS Secret and access policy | Approved existing HTTPS ingress and audience controls |
| `KUBE_CONTEXT`, private values/evidence/rollback paths | Explicit target and private operator storage |

Then run preflight, render/review, deploy through the approved delivery path, configure approved telemetry fan-out and run connected HTTPS verification. Existing-agent deployment does not configure platform OTel exports automatically. Preserve the current observability destination. Model/MCP connectivity, W3C trace propagation and server instrumentation must be checked on the target.

The stock existing-agent preflight expects kagent `1.0.0-alpha8`, Substrate `0.4.0-alpha1` and Agent API `v1alpha3`. Different workplace versions need a reviewed port, not an automatic platform upgrade.

Therefore the sequence is **imports + non-image build inputs → source build and registry publication → private work values → preflight and deployment → telemetry and connected acceptance**. A ready application image completes the build prerequisite; it does not alone prove platform, ingress or telemetry readiness.

## Sources

- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/image-lock.json
- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/Dockerfile
- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/scripts/build-image.sh
- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/deploy/chart/values.yaml
- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/RUNTIME-COMPARISON.md
- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/requirements-ops.txt
- https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/otel-agent-flow/scripts/platform-telemetry.py
