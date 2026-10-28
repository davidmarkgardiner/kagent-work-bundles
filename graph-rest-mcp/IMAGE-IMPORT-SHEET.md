# Image and offline-build prerequisites

There is **one application image to build internally**. It contains FastMCP and
the adapter; the same image can also run the optional synthetic REST fixture.
There is no separate upstream FastMCP server image to import, no PostgreSQL/AGE
server to deploy for the adapter, and no lab model/worker to import for an
existing workplace agent. The workplace Swagger service already exists.

## Exact upstream base (verified 2026-10-28)

| Artifact | Reference |
| --- | --- |
| Upstream base | `docker.io/library/python:3.12-slim-bookworm` |
| Multi-platform index | `sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337` |
| Linux amd64 manifest | `sha256:623674a14ef93d052bb9b0de4dbf5f28eb578a35263838941cc8aa43213c1487` |
| Linux arm64 manifest | `sha256:e0b3f8d16a5ccfbe602d5c94297e5dbcda2ec256edca2b80fcd44e39e1ff6feb` |
| Machine-readable lock | [image-lock.json](image-lock.json) |

Import only the target architecture or preserve the index and its required
children. Record the resulting internal repository and manifest digest; a
registry that rewrites manifests can change the digest. Pass that **verified
internal digest reference** as `BASE_IMAGE`. A tag alone is not the pin.
The old image IDs in `evidence/REPORT.md` are historical local IDs, not a public
registry artifact or the digest of this handoff revision.

## Two supported supply routes

**Connected approved build:** import the pinned base; build `Dockerfile` using
`requirements.lock` through an approved package source, then promote the complete
application image into the disconnected registry. The Dockerfile verifies hashes
and rejects source distributions. Internal PyPI configuration needs to be supplied
through approved build tooling; do not bake credentials into image layers.

**Disconnected build:** import the base **and** transfer the hash-checked runtime
wheelhouse. `Dockerfile.offline` installs with `--no-index --require-hashes
--only-binary=:all:` and its RUN steps have network disabled. No apt packages,
compilers or source builds are required. Hashes and all transitive runtime versions
are in `requirements.lock`; direct version choices are in `requirements.txt`.
Do not re-resolve dependencies inside work without reviewing and regenerating
the lock, wheels, tests and audit together.

## Prepare outside the air gap

Use Python 3.12 with pip and internet access on an approved staging machine:

```bash
python3.12 scripts/prepare_wheelhouse.py --arch amd64 --output /tmp/graph-wheels-amd64
```

For arm64, use `--arch arm64` and a different empty output directory. The script
selects Linux CPython 3.12 binary wheels regardless of the staging machine's
architecture, checks the lock hashes, and writes `manifest.json` with the lock hash
and every wheel SHA-256. Re-run it after any lock change. Transfer that directory
through the approved artifact process, and verify its hashes on receipt.
Wheels and image archives are deliberately absent from this GitHub source bundle;
downloading the repository ZIP alone does not satisfy the offline build inputs.

## Build inside the approved environment

From the bundle directory, with the target base already present internally:

```bash
mkdir wheelhouse
cp /tmp/graph-wheels-amd64/*.whl wheelhouse/
BASE_IMAGE='{{INTERNAL_BASE_IMAGE_AT_DIGEST}}'
APP_IMAGE='{{INTERNAL_APPLICATION_REPOSITORY}}:{{REVIEWED_TAG}}'
docker build --platform linux/amd64 --network=none --pull=false \
  --build-arg BASE_IMAGE="$BASE_IMAGE" -f Dockerfile.offline -t "$APP_IMAGE" .
docker run --rm --network=none "$APP_IMAGE" python -m pip check
```

Replace placeholders before use; use the matching platform/wheelhouse for arm64.
BuildKit must be available for `RUN --network=none`. BuildKit/registry metadata and
base acquisition are separate from RUN networking: the builder must already have
the base or reach the approved internal registry. These flags do not prove that
the whole build daemon has no external network access. Verify that at the actual
disconnected build host. The fresh handoff validation proves network-disabled
RUN steps, not the workplace registry, trust chain or firewall.

The application runs as UID/GID 10001. Its manifests disable privilege escalation,
drop capabilities, use a read-only root filesystem and omit Kubernetes API tokens.
For a private registry, add the existing approved pull identity/imagePullSecrets
to the workload according to workplace conventions.

## Promotion receipt (work agent fills privately)

| Required field | Value |
| --- | --- |
| Source revision / bundle hash | `{{REVIEWED_SOURCE_REVISION}}` |
| Platform | `{{linux/amd64_OR_linux/arm64}}` |
| Imported base repository and digest | `{{INTERNAL_BASE_IMAGE_AT_DIGEST}}` |
| Requirements lock SHA-256 | `{{LOCK_SHA256}}` |
| Wheelhouse manifest SHA-256 | `{{WHEEL_MANIFEST_SHA256}}` |
| Built application repository/tag | `{{INTERNAL_APPLICATION_REPOSITORY}}:{{REVIEWED_TAG}}` |
| Application **registry manifest digest** | `{{APPLICATION_MANIFEST_DIGEST}}` |
| SBOM, scan/signature policy and outcome | `{{APPROVED_SUPPLY_CHAIN_EVIDENCE}}` |
| Pull/start and direct MCP canary | `{{TARGET_ACCEPTANCE_RECEIPT}}` |

Push/promote only through the authorized build process, resolve the pushed digest,
and deploy `repository@sha256:...`. `docker inspect` local image ID, registry
manifest digest and multi-platform index digest are different identifiers.
No application image has been published to a registry by this bundle.

The current Python dependency audit is recorded in the handoff evidence. It is
not an OS-image scan, a permanent vulnerability warranty or workplace policy
approval; run the target registry's current image scan/SBOM/signature gates.

Official references: [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/),
[FastMCP HTTP deployment](https://gofastmcp.com/deployment/http),
[HTTPX explicit TLS trust](https://www.python-httpx.org/advanced/ssl/).
