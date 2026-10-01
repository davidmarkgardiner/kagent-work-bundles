# Work-agent task: build and publish the Azure DevOps MCP image

Use this source-only bundle to build inside work. No imported application image
is required. Read AGENTS.md and WORK-START-HERE.md before executing.

## Copy this task to the work agent

> Build the Azure DevOps MCP image from this extracted bundle and publish it to
> our nominated internal registry. Use Microsoft's official MCP 2.10.0 package
> pinned in app/package-lock.json, keeping the included HTTP bridge and draft-PR
> policy. Determine the approved build host, Linux node architecture, registry
> path, base image and npm/Debian sources from our existing configuration. Use
> approved internal mirrors when public downloads are blocked. Preserve unrelated
> work. Never put an Azure DevOps PAT or registry password in source, build args,
> image layers or logs. Use existing registry authentication.
>
> First confirm the build host can resolve every dependency. Build for the target
> architecture, run all protocol/policy tests with container networking disabled,
> run image-smoke.mjs offline with a read-only filesystem, and confirm native
> keytar loads. Only after those pass, push the image to the internal registry
> specified for this task. Report its full pull reference and registry manifest
> digest, test results, build-source identity and any mirror adaptations. Do not
> claim live Azure DevOps access based on offline catalog discovery.
>
> Prepare secret-free rendered Kubernetes manifests using an existing approved
> ModelConfig, then server-side dry-run against the nominated cluster when one
> is supplied. Preserve existing agents and gateway configuration. Do not deploy,
> install credentials or create work PRs as part of this build/publish task unless
> separately instructed. Leave deployment and the live draft-PR demo reviewable
> using WORK-START-HERE.md. If an actual dependency, permission or network route
> is missing, report the specific missing item; do not substitute a different MCP
> implementation, floating package version, or disabled TLS verification.

Required work-specific inputs are the internal image repository and approved
builder/dependency routes. The deployment phase additionally needs Kubernetes
context/namespace, existing ModelConfig, cloud organization/project/repository,
reviewed source/target branches and approved secret installation. Use private
configuration paths outside the public bundle.

## Concrete build/push sequence

From the extracted bundle directory, substitute the nominated internal registry:

```bash
ADO_WORK_IMAGE='{{INTERNAL_REGISTRY}}/azure-devops-mcp:2.10.0-work1'
docker build --platform linux/amd64 -t "$ADO_WORK_IMAGE" .
docker run --rm --platform linux/amd64 --network none --read-only \
  "$ADO_WORK_IMAGE" node --test
docker run --rm --platform linux/amd64 --network none --read-only \
  "$ADO_WORK_IMAGE" node image-smoke.mjs
docker run --rm --platform linux/amd64 --network none --read-only \
  "$ADO_WORK_IMAGE" node -e 'require("keytar"); console.log("native keytar loaded")'
docker push "$ADO_WORK_IMAGE"
```

This is the normal Dockerfile, not Dockerfile.offline: it builds all dependencies
at work. The offline Dockerfile requires an already-built dependencies image and
is useful for later adapter-only rebuilds.

For an approved mirrored base image, add:

```bash
--build-arg NODE_IMAGE='{{INTERNAL_REGISTRY}}/node:22-bookworm@sha256:{{APPROVED_BASE_DIGEST}}'
```

Use the right platform-specific digest. npm lockfile entries currently resolve
to registry.npmjs.org; merely setting npm's registry does not prove all locked
URLs resolve internally. Use the approved package mirror mechanism and verify
actual requests. Review any lockfile URL rewrites while retaining package
versions and integrity hashes. Debian sources need equivalent approved mirror
configuration in both Dockerfile stages. Keep mirror credentials out of image
layers; use work's existing secret-aware builder. If neither public access nor
complete mirrors are available, source ZIP alone cannot produce the image.

After pushing, record the digest printed by the registry and use
`{{INTERNAL_REGISTRY}}/azure-devops-mcp@sha256:{{IMAGE_DIGEST}}` in private config.
A Docker local image ID is not the registry manifest digest.

## Role of the official repository ZIP

Official source: https://github.com/microsoft/azure-devops-mcp
Pinned source ZIP: https://github.com/microsoft/azure-devops-mcp/archive/refs/tags/v2.10.0.zip

That ZIP contains Microsoft's server source. It does not contain our HTTP bridge,
policy, image recipe or kagent work handoff. To reproduce our demo, give the work
agent **this bundle's ZIP**; it fetches the official locked npm release at build
time. Downloading the upstream ZIP is optional for source review/provenance.

If work policy mandates compiling upstream TypeScript from source instead of
using the released npm package, treat that as a reviewed build adaptation:
retain the official source/version identity, compile using approved dependencies,
install runtime/native dependencies and rerun discovery/schema/policy checks.
The included Dockerfile tests the released npm artifact; it does not claim a
source-ZIP compilation has been verified or is identical to that artifact.
