# Legacy kagent 0.7 image builds

Build these images in the approved internal pipeline. The Dockerfiles have no public base default and do not download dependencies at runtime. They are build recipes, not prebuilt or workplace-verified images.

## Prepare the approved inputs

Supply these inputs through the normal software intake process.

- A digest-pinned internal CPython 3.12-compatible base with the standard library, CA certificates, and `python` on PATH for the helper image. The controllers, fixed MCP backend, and viewer use standard-library Python. Their reviewed code is supplied through generated ConfigMaps.
- A digest-pinned internal runtime base for a Linux collector binary. Build the collector from the reviewed source version and vendored Go dependencies for the target architecture. Include OTLP gRPC and HTTP receivers, batch processor, and `otlp_http` exporter. Verify those component names against the generated collector configuration. The existing tested distro was 0.146.0. A custom build needs its own compatibility proof.
- A digest-pinned internal Python base with `pip` and all approved OS libraries for the exact installed kagent runtime. Build wheels for that exact kagent source revision and its transitive dependencies. Supply a fully pinned, hash-locked `requirements.lock` and wheelhouse. Match the target Python version, OS ABI, and CPU architecture. The tested upstream v0.7.13 build used Python 3.13, while the helper controllers use Python 3.12-compatible code.

Preserve source licences, source commit hashes, dependency locks, SHA256 inventories, SBOMs, vulnerability results, and build provenance. Inspect internal base images too. A private registry name does not prove a reviewed build.

The native-runtime recipe is an alternative assembly from locally supplied wheels. It is not a drop-in guarantee for every kagent version. Prove the native CLI, installed plugin imports, configuration loading, credentials, telemetry, and writable paths against your actual controller before promotion. If the approved runtime needs additional OS dependencies, build those into the base through the internal pipeline. Do not install them during Pod startup.

## Build without dependency downloads

Set these variables to approved internal values. Import base images into the isolated builder before running the commands. Keep real values outside the public bundle.

```bash
export PYTHON_HELPER_BASE='{{INTERNAL_HELPER_BASE_AT_SHA256}}'
export PYTHON_AGENT_BASE='{{INTERNAL_AGENT_PYTHON_BASE_AT_SHA256}}'
export COLLECTOR_BASE='{{INTERNAL_COLLECTOR_BASE_AT_SHA256}}'
export HELPER_IMAGE='{{INTERNAL_HELPER_BUILD_TAG}}'
export COLLECTOR_IMAGE='{{INTERNAL_COLLECTOR_BUILD_TAG}}'
export NATIVE_RUNTIME_IMAGE='{{EXACT_CONTROLLER_COMPOSED_INTERNAL_RUNTIME_TAG}}'
export COLLECTOR_CONTEXT='/absolute/private/path/collector-context'
export RUNTIME_CONTEXT='/absolute/private/path/runtime-context'
```

Put the reviewed static executable at `$COLLECTOR_CONTEXT/otelcol`. Verify its supplied SHA256 before building. Put the local wheels and lock at `$RUNTIME_CONTEXT/wheelhouse/` and `$RUNTIME_CONTEXT/requirements.lock`.

From the bundle root, build the images.

```bash
docker build --network=none --pull=false \
  --build-arg "APPROVED_PYTHON_BASE=$PYTHON_HELPER_BASE" \
  -f build/Dockerfile.helpers -t "$HELPER_IMAGE" build
docker build --network=none --pull=false \
  --build-arg "APPROVED_RUNTIME_BASE=$COLLECTOR_BASE" \
  -f build/Dockerfile.collector -t "$COLLECTOR_IMAGE" "$COLLECTOR_CONTEXT"
docker build --network=none --pull=false \
  --build-arg "APPROVED_PYTHON_BASE=$PYTHON_AGENT_BASE" \
  -f build/Dockerfile.kagent-runtime.legacy-0.7 -t "$NATIVE_RUNTIME_IMAGE" "$RUNTIME_CONTEXT"
```

`--network=none` disables network for build steps. It does not prevent the image builder from resolving or fetching a `FROM` image. Enforce the builder's external-network block separately and prove that a clean builder uses only approved internal inputs. Do not add public package mirrors, disable TLS verification, or rely on warm caches to pass.

Push through the approved internal registry process, record the registry manifest digests, and use those exact helper and collector digests in the private installation config. Do not copy a local Docker config digest into a registry manifest-digest field.

The ordinary Declarative Agent API supplies an image registry prefix. The existing controller chooses its runtime repository and tag. Preserve that exact composition. Record the corresponding approved manifest digest, prevent tag replacement through registry policy or approved admission enforcement, and compare the actual Pod `imageID` before acceptance. Do not add an unsupported arbitrary `image` field or change shared controller defaults just for the demo.

## Prove offline closure

Run the helper Python import smoke, collector config validation, and native CLI under a fresh no-network container. Run the native request in the isolated target using only approved internal model, Git, DNS, API, and telemetry services. The model must be available through an approved internal route. The existing controller, UI, gateway, Flux and model services also belong in the target's image and dependency inventory even when this package does not install them.

Prepare local Python tooling from an internal wheelhouse too.

```bash
python3 -m venv "$PRIVATE_VENV"
"$PRIVATE_VENV/bin/python" -m pip install --no-index \
  --find-links "$APPROVED_TOOLING_WHEELHOUSE" -r requirements.txt
```

The bundle pins the two top-level tooling packages in `requirements.txt`; it does not contain every transitive wheel or a full tooling hash lock. Generate and review that complete lock inside the approved intake pipeline before transfer. A source ZIP plus these recipes is not proof of air-gap closure.
