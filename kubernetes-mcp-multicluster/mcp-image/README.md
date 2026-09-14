# Work guide: build the air-gapped Kubernetes MCP image for AKS

This is the image-build gate for the AKS fleet proof of concept. Complete it
in the work image pipeline before deploying the rest of the bundle.

The image contains only:

- the approved Kubernetes MCP server base image; and
- the Azure `kubelogin` exec-plugin binary at
  `/usr/local/bin/kubelogin`.

Do not add Azure CLI or `kubectl` to this image. Those tools are required by
the separate credential-refresh Job image in `../credential-refresh-image/`.
The MCP pod receives Azure Workload Identity environment variables and a
projected service-account token from AKS. When it uses an exec-format context
from the mounted kubeconfig, that context runs this `kubelogin` binary to
obtain a short-lived token.

## 1. Pin the inputs

This bundle currently pins:

| Input | Approved coordinate |
|---|---|
| Kubernetes MCP base | `quay.io/containers/kubernetes_mcp_server:v0.0.66` |
| Azure kubelogin | `v0.2.19` |
| Linux AMD64 archive | `kubelogin-linux-amd64.zip` |
| Archive SHA-256 | `ebaeff02aa899c5cae6a2b954b64fc02738185319df2570f7dc053451efa4b2f` |
| Binary path inside archive | `bin/linux_amd64/kubelogin` |
| Binary path in final image | `/usr/local/bin/kubelogin` |
| Suggested derived tag | `v0.0.66-kubelogin-v0.2.19` |

The release archive and its checksum file are published on the official
[Azure kubelogin v0.2.19 release](https://github.com/Azure/kubelogin/releases/tag/v0.2.19).
Use the `linux-arm64` asset instead only if the Kubernetes nodes run ARM64.
Never copy a macOS binary from the staging workstation into a Linux image.

Before adopting a newer helper, review its release, update the pin and digest
in this guide, rebuild, scan, and repeat the runtime checks below. Do not
silently resolve `latest` in the pipeline.

## 2. Stage the artifacts on a connected machine

Run this in an empty staging directory on a connected Linux machine:

```bash
export KUBELOGIN_VERSION=v0.2.19
export KUBELOGIN_ARCH=amd64

curl -fL -O \
  "https://github.com/Azure/kubelogin/releases/download/${KUBELOGIN_VERSION}/kubelogin-linux-${KUBELOGIN_ARCH}.zip"
curl -fL -O \
  "https://github.com/Azure/kubelogin/releases/download/${KUBELOGIN_VERSION}/kubelogin-linux-${KUBELOGIN_ARCH}.zip.sha256"

sha256sum --check "kubelogin-linux-${KUBELOGIN_ARCH}.zip.sha256"
unzip "kubelogin-linux-${KUBELOGIN_ARCH}.zip"
install -m 0555 "bin/linux_${KUBELOGIN_ARCH}/kubelogin" ./kubelogin
sha256sum ./kubelogin > kubelogin.binary.sha256
file ./kubelogin
```

The archive check must print `OK`. For the pinned AMD64 archive, the calculated
archive digest must equal the value in the table above. On macOS, use
`shasum -a 256` for the independent digest check, but do not try to execute
the Linux binary there.

The Kubernetes MCP image has already been staged according to the main bundle
guide. Preserve its immutable source digest when it is imported into the work
registry:

```bash
docker pull quay.io/containers/kubernetes_mcp_server:v0.0.66
docker image inspect quay.io/containers/kubernetes_mcp_server:v0.0.66 \
  --format '{{json .RepoDigests}}'
docker save --output kubernetes_mcp_server-v0.0.66.tar \
  quay.io/containers/kubernetes_mcp_server:v0.0.66
sha256sum kubernetes_mcp_server-v0.0.66.tar \
  > kubernetes_mcp_server-v0.0.66.tar.sha256
```

Transfer these items through the approved air-gap process:

```text
kagent-public bundle or repository checkout
kubelogin
kubelogin.binary.sha256
kubelogin-linux-amd64.zip
kubelogin-linux-amd64.zip.sha256
kubernetes_mcp_server-v0.0.66.tar
kubernetes_mcp_server-v0.0.66.tar.sha256
```

The extracted binary is convenient for the pipeline, while retaining the
original release location, archive, and checksums gives the work change an
auditable provenance trail.

## 3. Prepare the offline build context

In the work checkout, go to this directory:

```bash
cd work-agent-bundles/kubernetes-mcp-multicluster/mcp-image
```

Copy the approved extracted binary beside the Dockerfile. The final directory
must look like this:

```text
mcp-image/
├── Dockerfile
└── kubelogin
```

Verify it again before building:

```bash
cd /path/to/staged/artifacts
sha256sum --check kubelogin.binary.sha256
install -m 0555 kubelogin \
  /path/to/kagent-public/work-agent-bundles/kubernetes-mcp-multicluster/mcp-image/kubelogin
file /path/to/kagent-public/work-agent-bundles/kubernetes-mcp-multicluster/mcp-image/kubelogin
```

The binary and archives are ignored by Git. Do not commit binary artifacts to
this public repository.

## 4. Import the base and build without internet access

Load the approved archive if the pipeline has not already mirrored the image:

```bash
cd /path/to/staged/artifacts
sha256sum --check kubernetes_mcp_server-v0.0.66.tar.sha256
docker load --input kubernetes_mcp_server-v0.0.66.tar
```

Return to `mcp-image/` and set placeholders to work registry coordinates. The
base may be the loaded public coordinate or its approved internal mirror:

```bash
export KUBERNETES_MCP_BASE_IMAGE={{INTERNAL_REGISTRY}}/{{MIRROR_PROJECT}}/kubernetes_mcp_server:v0.0.66
export KUBERNETES_MCP_DERIVED_IMAGE={{INTERNAL_REGISTRY}}/{{PROJECT}}/kubernetes_mcp_server:v0.0.66-kubelogin-v0.2.19

docker build --pull=false --network=none \
  --build-arg KUBERNETES_MCP_BASE_IMAGE="$KUBERNETES_MCP_BASE_IMAGE" \
  --build-arg KUBELOGIN_VERSION=v0.2.19 \
  --tag "$KUBERNETES_MCP_DERIVED_IMAGE" \
  .
```

If the build service uses BuildKit directly, keep the equivalent controls:
the build must use the imported base, disable pulling, disable build-network
access, and target the same architecture as the AKS node pool. For an AMD64
node pool, a buildx equivalent is:

```bash
docker buildx build --platform linux/amd64 --pull=false --network=none --load \
  --build-arg KUBERNETES_MCP_BASE_IMAGE="$KUBERNETES_MCP_BASE_IMAGE" \
  --build-arg KUBELOGIN_VERSION=v0.2.19 \
  --tag "$KUBERNETES_MCP_DERIVED_IMAGE" \
  .
```

`--network=none` blocks network access from Dockerfile `RUN` steps; it does not
disable the builder's base-image resolver. A `buildx` builder using the
`docker-container` driver cannot automatically see an image loaded only into
the host Docker daemon. Mirror the base in an internal registry reachable by
that builder, or import it into the builder's own content store. A standard
Docker builder can use the locally loaded base. The Dockerfile's default base
is an intentionally invalid coordinate, so omitting the required build
argument fails closed.

The Dockerfile performs no download. Its build-time `kubelogin --version`
check deliberately fails when the binary is for the wrong architecture or is
not executable.

## 5. Prove the derived image contract

Run all checks in the work pipeline before pushing:

```bash
docker run --rm --entrypoint /usr/local/bin/kubelogin \
  "$KUBERNETES_MCP_DERIVED_IMAGE" --version
docker run --rm --entrypoint /usr/local/bin/kubelogin \
  "$KUBERNETES_MCP_DERIVED_IMAGE" get-token --help

docker image inspect "$KUBERNETES_MCP_DERIVED_IMAGE" \
  --format 'platform={{.Os}}/{{.Architecture}} user={{json .Config.User}} entrypoint={{json .Config.Entrypoint}} cmd={{json .Config.Cmd}}'
docker image inspect "$KUBERNETES_MCP_BASE_IMAGE" \
  --format 'platform={{.Os}}/{{.Architecture}} user={{json .Config.User}} entrypoint={{json .Config.Entrypoint}} cmd={{json .Config.Cmd}}'
```

Acceptance criteria:

- `kubelogin --version` reports `v0.2.19`;
- `get-token --help` exits successfully;
- the target platform matches the AKS node pool;
- the derived image preserves the base image user, entrypoint, and command;
- `/usr/local/bin/kubelogin` is executable by the non-root runtime user;
- the container scan passes the work policy; and
- no credential, tenant ID, subscription ID, client ID, token, or kubeconfig is
  present in any layer.

Push the exact accepted image and record its immutable digest:

```bash
docker push "$KUBERNETES_MCP_DERIVED_IMAGE"
docker image inspect "$KUBERNETES_MCP_DERIVED_IMAGE" \
  --format '{{json .RepoDigests}}'
```

Keep a work-side receipt with the Git commit, base image digest, archive
digest, extracted binary digest, final image tag and digest, target platform,
scan result, and the output of the two runtime checks.

## 6. Point the bundle at the internal image

Return to the bundle directory and edit the one ignored customization file:

```bash
cd ..
cp -n work-values.env.template work-values.env
```

Set these values to the pushed work coordinate:

```dotenv
IMAGE_REGISTRY={{INTERNAL_REGISTRY}}
IMAGE_REPOSITORY={{PROJECT}}/kubernetes_mcp_server
IMAGE_VERSION=v0.0.66-kubelogin-v0.2.19
APPROVED_IMAGE_PREFIX={{INTERNAL_REGISTRY}}/{{PROJECT}}/
```

Do not put the image pull secret, kubeconfig, Azure credentials, or registry
password in `work-values.env`. Configure the existing namespace/image-pull
mechanism separately.

Continue with the main [bundle deployment guide](../README.md). The Helm chart
does not need the kubeconfig on the machine that runs `helm upgrade`. It only
renders a reference to the named Kubernetes Secret; the credential-refresh
Job creates and updates that Secret in the cluster.

## 7. Prove it in the running MCP pod

After the bootstrap credential Job and Helm deployment complete:

```bash
kubectl --context {{MANAGEMENT_CONTEXT}} -n {{MCP_NAMESPACE}} \
  exec deployment/{{MCP_NAME}} -- /usr/local/bin/kubelogin --version

kubectl --context {{MANAGEMENT_CONTEXT}} -n {{MCP_NAMESPACE}} \
  get pod -l app.kubernetes.io/instance={{MCP_NAME}} \
  -o jsonpath='{range .items[*]}{.metadata.name}{" image="}{.status.containerStatuses[0].image}{" imageID="}{.status.containerStatuses[0].imageID}{"\n"}{end}'

kubectl --context {{MANAGEMENT_CONTEXT}} -n {{MCP_NAMESPACE}} \
  exec deployment/{{MCP_NAME}} -- \
  sh -c 'test -r /config/kubeconfig && test -x /usr/local/bin/kubelogin'
```

Then run `../scripts/smoke.sh` and invoke the kagent Agent through agentgateway
as described in the main guide. Image presence alone is not the proof: a
successful MCP call against an AKS context confirms that the mounted
kubeconfig, workload identity projection, `kubelogin`, target RBAC, MCP,
agentgateway, and kagent path work together.

## Failure guide

| Symptom | Likely cause | Action |
|---|---|---|
| `exec format error` during build | Binary architecture differs from build target | Stage the matching `linux-amd64` or `linux-arm64` asset |
| `kubelogin: executable file not found` | Derived image was not deployed, or binary path changed | Check `IMAGE_*`, pod `imageID`, and `/usr/local/bin/kubelogin` |
| `AADSTS70021` or federated credential failure | ServiceAccount issuer, subject, or audience does not match the UAMI federated credential | Check the AKS Workload Identity binding; do not bake credentials into the image |
| MCP starts but AKS calls return unauthorized | Exec kubeconfig, UAMI permissions, projected token, or target RBAC is wrong | Inspect the refresh Job and MCP logs, then test the same context through the MCP smoke path |
| Pipeline attempts an internet pull | Base coordinate is absent locally or build controls are incomplete | Import or mirror the pinned base and enforce `--pull=false --network=none` |

Do not fix these failures by using `az aks get-credentials --admin`, adding a
service-principal secret to the image, switching to `latest`, or downloading
tools during the image build.
