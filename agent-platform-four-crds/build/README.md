# Build and import for kagent 1.0

The requested build target is **kagent 1.0.0-alpha17**, the latest published 1.0 release checked on 28 October 2026. Its source pin, chart checksums and native runtime image are recorded in [kagent-1.0-target.json](kagent-1.0-target.json). Use fixed versions and digests, not a moving `latest` tag.

**Build preparation is defined; the legacy installer still needs a 1.0 port.** Start the work agent with [KAGENT-1.0-WORK-AGENT-PROMPT.md](../KAGENT-1.0-WORK-AGENT-PROMPT.md). The existing `package.py`, `private_install.py`, ordinary MCP demo and copied controllers generate or inspect kagent 0.7.13 objects. They do not become compatible through an image or API-version substitution.

## Prepare these inputs first

| Input | Build or import action |
| --- | --- |
| Native Agent runtime | Import the complete official Go ADK image below into the approved internal registry. No Python wheel build is needed for this runtime. Preserve the manifest index and required target-platform manifests, or record the selected platform digest separately. |
| Custom content/onboarding helpers | Build `Dockerfile.helpers` with an approved digest-pinned Python 3.12-compatible base. These Python helpers are separate from the native Agent runtime. Port their API assumptions before deployment. |
| OTel collector | Reuse a compatible approved internal collector, or build `Dockerfile.collector` with an approved base and reviewed binary. Match OTLP receivers and exporters to the eventual native configuration. |
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

## Release the installation only after the port passes

Require native `AgentTemplate` and `Agent.spec.harnessRef`, approved `Harness` configuration, immutable skill sources, bounded knowledge delivery and matching native invocation/telemetry tests. Preserve the four custom CRDs and their immutable release contracts. Do not claim that existing 0.7 tests validate this port.

Record build/import provenance separately from server schema validation and fresh native runtime acceptance. The full image inventory and workplace proof remain target gates. See the work-agent prompt for the exact port and acceptance tasks.

Upstream release: https://github.com/kagent-dev/kagent/releases/tag/v1.0.0-alpha17
