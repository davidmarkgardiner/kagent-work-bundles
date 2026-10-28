# Build and import for kagent 1.0

The POC targets **kagent 1.0.0-alpha17**, the latest published 1.0 release checked on 28 October 2026. Its source pin, chart checksums and native runtime image are recorded in [kagent-1.0-target.json](kagent-1.0-target.json). Use fixed versions and digests, not a moving `latest` tag.

The native adapter, content publisher, GoldenScenario runner and saved alpha17 lab receipts are included in `implementation/platform/skills-registry/native/`. Follow [POC-QUICKSTART.md](../POC-QUICKSTART.md) to get one skill and one knowledge package working first. Choose any permitted namespace with suitable namespace-local Harness and ModelConfig dependencies. The root ordinary-Agent installer remains a separate legacy path.

## Prepare these inputs first

| Input | Build or import action |
| --- | --- |
| Native Agent runtime | Import the complete official Go ADK image below into the approved internal registry. No Python wheel build is needed for this runtime. Preserve the manifest index and required target-platform manifests, or record the selected platform digest separately. |
| Custom content/onboarding helpers | Build `Dockerfile.helpers` with an approved digest-pinned Python 3.12-compatible base. These Python helpers are separate from the native Agent runtime. Use the included native renderer and select this image in both generated Deployments. |
| Skill and KnowledgeBase content | Publish two data-only OCI images with the bundled native `publish.py`, then copy their layouts with ORAS. No executable or OS base image is needed for either content package. |
| OTel collector | Optional for the first functional POC. Reuse a compatible internal collector or build `Dockerfile.collector` when adding the OTel view. |
| Existing kagent platform | Inventory controller, UI, sandbox guest, selected Harness runtime and any enabled tools or init containers from the actual rendered alpha17 platform configuration. Mirror missing images through the approved intake process. Do not reinstall the shared platform. |
| Substrate | The alpha17 source pins `go.ate.dev/substrate v0.6.0-alpha3`. Verify the approved matching platform, identity, database, storage, WorkerPool and sandbox runtime assets. Images alone do not supply these prerequisites. |
| Charts and local tools | Transfer the two checksum-pinned kagent charts in the JSON lock when needed for offline inspection. Supply approved Helm, kubectl and the helper tooling wheelhouse. Do not upgrade the workplace platform as part of intake. |

Import this exact native runtime:

```text
ghcr.io/kagent-dev/kagent/golang-adk@sha256:d20d411759d7bb549f00b7d6e8d669b91694aeb57dce847dcd2cbb68aa0d45f3
```

The official chart's built-in Harness catalog supplies this digest. The registry index was independently checked and contains Linux AMD64 and ARM64 manifests. Record the internal destination and manifest digests after copying. The stock runtime already implements the release's native contract; importing it is the preferred route.

For an approved source rebuild, use commit `8392184232e9c78196433a34b1fd3b33db5fcb97`, Go `1.27.3`, and the upstream `go/Dockerfile` with `BUILD_PACKAGE=adk/cmd/main.go`. Its stock recipe downloads modules and Alpine packages and uses an unpinned builder. An offline rebuild must first replace those inputs with approved pinned bases and reviewed vendored dependencies. Record its new digest and configure the native Harness image through the approved platform process.

## Keep legacy build inputs separate

The old Python Agent build is now [Dockerfile.kagent-runtime.legacy-0.7](Dockerfile.kagent-runtime.legacy-0.7), with its original instructions in [LEGACY-0.7-BUILD.md](LEGACY-0.7-BUILD.md). Do not use that image as the alpha17 native runtime. Legacy `imageRegistry` configuration and `sitecustomize.py` tracing hooks are not the 1.0 runtime interface.

## Deploy the first POC

Use native `resources.py`, `publish.py` and `run_golden.py` from the bundled native directory. Preserve its immutable release checks and existing platform dependencies. The quickstart covers helper-image overrides, removal of lab control-plane scheduling, source-controller routing and namespace selection. A new CI pipeline and dashboard are not prerequisites.

The saved lab receipts show this implementation working on alpha17. Run a fresh native acceptance session after deployment to establish the workplace result. Defer BYO-agent onboarding until this first skill/knowledge proof passes.

Upstream release: https://github.com/kagent-dev/kagent/releases/tag/v1.0.0-alpha17
