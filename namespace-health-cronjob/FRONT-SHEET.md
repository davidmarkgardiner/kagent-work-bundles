# Namespace health: image-build handoff

**Correction — 12 October 2026:** the GitHub bundle contains the application
source, Dockerfile, dependency lock file and wheel-preparation script. It does
**not** contain Python wheel binaries for either architecture. Earlier front
sheet wording saying six amd64 wheels were included is obsolete.

**First milestone: try to build and smoke-test the current Linux amd64 image
using our normal workplace image-build process.** David will supply an example
repository or pipeline. Inspect that first and reuse its approved builder,
registry, package sources, certificate configuration and credential handling.
A documented build blocker is an acceptable outcome.

Source bundle:
https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/namespace-health-cronjob

## Build approach

1. Use the current bundle's `src/`, `Dockerfile`, `requirements.lock` and
   `scripts-prepare-wheelhouse.sh`. Record the source revision. The historical
   October 7 image predates selective publication; do not reuse it as the new
   implementation.
2. Identify an approved Python 3.12, Linux amd64 base. Prefer an internal mirror
   of the Dockerfile's digest-pinned `python:3.12-slim-bookworm` image. Change
   `FROM` to the approved internal reference where necessary; simply importing
   the base into a registry does not update the Dockerfile reference.
3. Configure pip on the approved packaging host to use the workplace package
   index and CA/authentication setup, then run
   `bash scripts-prepare-wheelhouse.sh amd64` from the bundle directory. The
   script uses pip's configuration; it does not discover internal sources.
   Alternatively, import the exact wheels through the approved artifact route.
   Put `wheelhouse/amd64/` in the Docker build context. The script verifies
   filenames and hashes; Docker installs locally with `--no-index` and
   `--require-hashes`, without downloading packages during the build.
4. Attempt a build through the supplied pipeline. Inspect any error and make
   one targeted retry if the cause is clear and fixable. If still blocked,
   report the exact missing artifact, access requirement or incompatibility.
   Do not spend time on repeated blind retries or silently relax pinned hashes.

The six pinned dependencies are `requests==2.32.5`,
`confluent-kafka==2.11.1`, `certifi==2026.7.22`,
`charset-normalizer==3.5.2`, `idna==3.20` and `urllib3==2.8.0`.
All six amd64 wheels were downloaded and checksum-verified from public PyPI
on 12 October; availability in the workplace mirror remains to be checked.

## If an existing base image is easier

An approved internal image with Python and some dependencies already installed
can reduce what must be fetched. Check Python version, Linux architecture,
glibc compatibility, installed package versions and Kafka authentication
support first. Reuse matching dependencies and obtain only what is missing.
The original Dockerfile still copies a wheelhouse, so using preinstalled
packages requires a reviewed Dockerfile adaptation; changing `FROM` alone is
not sufficient. Record the base digest and any package/version differences.
Treat changed versions as a separate candidate requiring validation.

## Evidence to return, then stop

- Pipeline/build reference, source revision, base digest and final image digest
  if the approved pipeline publishes it.
- Behavior-test result: `python3 -m unittest discover -s tests -p 'test_*.py'`.
- Inside the built image, successful `python -m pip check` and
  `python -c 'import assess,collect,publish,receipt,confluent_kafka,requests; print("image imports OK")'`.
- If blocked: the exact error, affected package/base image, attempted fix and
  smallest next action. Keep credentials and internal details in private evidence.

This milestone is image build and smoke validation only. Deployment is a later
step using `WORK-AGENT-WALKTHROUGH.md`: exactly two approved namespaces,
selective Kafka publication and receipt-only Argo. A successful build does not
prove Kubernetes/Kafka connectivity. Do not deploy, unsuspend the CronJob or
add agent calls/remediation as part of this build attempt.
