# Azure DevOps MCP → kagent: isolated-network work bundle

Replicate the proven lab path: user → existing kagent/model route → authenticated
HTTP bridge → official Microsoft Azure DevOps MCP 2.10.0 over stdio → Azure
DevOps Services. The adapter permits eight read tools plus one optional,
exactly scoped draft-PR creation tool. This bundle does not deploy kagent,
agentgateway, a model, or broad execution permissions.

The lab created a real draft PR and independently checked the diff. Work-side
connectivity, installed CRDs, image policy and end-to-end behavior must be
verified separately. See `evidence/lab-pr-create.json` and `evidence/build.json`.

## Which isolation model do you have?

| Work network | Outcome |
|---|---|
| No public image/package downloads; approved Azure DevOps HTTPS egress | Use the complete image from an internal registry. No startup package downloads. |
| Cluster has no public egress; approved private route to a connected tool zone | Host the same bridge in that zone and route kagent through the approved gateway. Authenticate/TLS that route and adjust Host/NetworkPolicy configuration. |
| Fully disconnected, with neither Azure DevOps nor a connected tool zone reachable | Image transfer enables local tests/catalog discovery, not live cloud PR creation. |
| Internal Azure DevOps Server/TFS | This exact Microsoft MCP implementation is not supported. Its installed 2.10.0 entrypoint constructs `https://dev.azure.com/<org>` and PAT host validation excludes internal hosts. An on-prem adapter requires separate design and validation. |

Upstream support reference: https://github.com/microsoft/azure-devops-mcp/blob/main/docs/FAQ.md

## 1. Build inside work, or build/export on a connected machine

If image import is unavailable, give the work agent this source bundle and
[WORK-AGENT-BUILD-INSTRUCTIONS.md](WORK-AGENT-BUILD-INSTRUCTIONS.md). It can build
and push to your internal registry using approved dependency sources; no
prebuilt application image is required.

For the image-transfer alternative, from this bundle directory:

```bash
./build-and-export.sh /absolute/path/outside/repo/ado-mcp-transfer
```

It builds Linux **amd64** images, runs offline tests and checks the native keytar
module, then exports images, this source bundle, SHA-256 checksums and image IDs.
Transfer through your approved process. No organization values or secrets enter
the build. Review/scan the image through the normal work registry pipeline.

The exported application image is ready to use: you do not need to rebuild it.
It contains Node, the locked npm dependencies, compiled Linux keytar and its
libsecret runtime libraries, plus the bridge/policy. The lab used a Node base
image with online init-container installation; that base image alone is not a
replication artifact. This bundle removes all runtime `apt`, `npm` and `npx`.

The Node base is digest pinned and npm is lockfile pinned. Debian build-time
packages come from current repositories, so a later connected rebuild may differ.
Treat the transferred image digest as the immutable release. Save package/SBOM
and vulnerability evidence through your approved tooling. The image uses the full
Bookworm Node base; size optimization is a separate change.

## 2. Import and mirror inside work

On the work-side Docker host, from the transferred directory:

```bash
shasum -a 256 -c SHA256SUMS
# On Linux, sha256sum -c SHA256SUMS is equivalent.
docker image load -i azure-devops-mcp-images.tar
docker run --rm --network none azure-devops-mcp:2.10.0-poc1 node --test
docker tag azure-devops-mcp:2.10.0-poc1 '{{INTERNAL_REGISTRY}}/azure-devops-mcp:2.10.0-poc1'
docker push '{{INTERNAL_REGISTRY}}/azure-devops-mcp:2.10.0-poc1'
```

Use the **registry manifest digest returned by push**, not the Docker image
configuration ID from `image-ids.txt`, in Kubernetes. Registry access/sign-in is
work-specific. Attach the existing approved imagePullSecret to the pod if needed.
Do not put registry credentials in this bundle.

### Optional: rebuild application source offline

After loading both images, extract the source archive and enter that directory:

```bash
docker build --platform linux/amd64 --network none --pull=false \
  -f Dockerfile.offline \
  --build-arg DEPENDENCIES_IMAGE=azure-devops-mcp-dependencies:2.10.0-poc1 \
  -t azure-devops-mcp:work-reviewed .
docker run --rm --network none azure-devops-mcp:work-reviewed node --test
```

This rebuild copies reviewed application source onto the imported dependencies
image. No package registry or Debian mirror is needed. `--network none` disables
build-step networking; it does not prohibit Docker metadata resolution. Load the
exact local dependencies tag first and use a local builder with `--pull=false`;
a remote builder needs the same image preloaded or accessible internally.

If package.json/package-lock.json or Node/native ABI changes, regenerate the
matching dependencies image on an approved connected builder, or use internal
npm/Debian mirrors. Do not copy macOS node_modules into Linux. The included
base-image digest is amd64-specific; for ARM64 select a verified ARM64 base,
rebuild native modules and repeat validation. This bundle only proves amd64.

## 3. Prepare the existing platform and network

Already required: installed kagent CRDs/controller, a reachable approved
ModelConfig, the controller-generated Agent runtime image mirrored internally,
and any existing agentgateway/model images. Mirroring this MCP image does not
mirror those platform components. Inventory actual images before rollout:

```bash
kubectl --context '{{KUBE_CONTEXT}}' -n '{{NAMESPACE}}' get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{": "}{range .spec.containers[*]}{.image}{" "}{end}{"\n"}{end}'
```

The bundle was validated against kagent 0.7.13. Inspect installed CRDs and use
server-side dry-run; do not assume current upstream examples match work's version.
The sample NetworkPolicy ingress selectors must match actual controller and
Agent pod labels. For another namespace verify controller selection; podSelector
alone selects only pods in the policy namespace.

For PAT mode this bundle explicitly sets `ADO_TENANT=common` to skip upstream's
organization-tenant discovery request. It does not invoke Azure CLI or interactive
Entra login. The minimal PR path needs DNS, trusted TLS and HTTPS to
`dev.azure.com`; identities or other selected operations can additionally use
`vssps.dev.azure.com` and `almsearch.dev.azure.com`. This list comes from the pinned
package's PAT destination allowlist, not a comprehensive firewall specification.
Use approved network traces to establish the endpoints for your actual workflow.

Node 22 proxy behavior is not assumed here. If the only route is an explicit
HTTP proxy, test both SDK fetch and Azure DevOps client calls with your approved
proxy configuration before claiming connectivity. Merely adding HTTPS_PROXY is
not proven. For a corporate CA, mount the public CA bundle and set
NODE_EXTRA_CA_CERTS to its path; verify both clients. Never disable TLS checking.
The manifest includes ingress restriction but no egress policy: adapt existing
work egress controls rather than applying guessed service IP ranges. LLM routes
also need a local/reachable model or approved model egress.

## 4. Select a sandbox repository and review manifests

Use a work-approved identity limited to a sandbox repository. PAT Code Read &
Write enables Git reads and PR creation; project discovery and optional build,
work-item/wiki reads may require separate read scopes. No Full Access PAT is
required. PAT scopes and repository permissions both apply. Read tools remain
organization/identity-scoped, not confined by the write scope.

Prepare a source branch containing a small reviewed change before requesting a
PR. The lab scaffold used Git REST API; **the agent creates the PR, not commits**.
The bundle deliberately gives the agent no generic file-push/branch-write tool.
For example, in your existing sandbox checkout:

```bash
git switch -c '{{SOURCE_BRANCH}}'
# Add/review a small Markdown file, then commit and push that branch normally.
```

Copy `config.example.json` to a private work path and set every placeholder.
Branch values omit `refs/heads/`. Supply a complete internal image digest and an
existing approved ModelConfig. Configuration contains no credentials; keep work
organization/repository/registry values out of this public repository.

```bash
mkdir -p /absolute/private/work-output
python3 render.py --config /absolute/private/work-config.json \
  > /absolute/private/work-output/azure-devops-mcp.json
kubectl --context '{{KUBE_CONTEXT}}' apply --dry-run=server \
  -f /absolute/private/work-output/azure-devops-mcp.json
```

Rendered objects use new names: `azure-devops-mcp` Deployment/Service,
`azure-devops-scoped` RemoteMCPServer, `azure-devops-pr` Agent. Check name
collisions first. Review through your usual Flux/GitOps process for permanent
installation. No control-plane toleration or online init container is included.

## 5. Install secrets and deploy through your approved process

Prefer the existing secret manager/ExternalSecret integration. For a controlled
manual trial, create the namespace beforehand and run the hidden-input helper:

```bash
python3 install-secrets.py --context '{{KUBE_CONTEXT}}' --namespace '{{NAMESPACE}}'
```

It creates/updates only Kubernetes Secrets `azure-devops-mcp-pat` and
`azure-devops-mcp-bridge-key`. It passes secret data on stdin, never CLI arguments,
and uses server-side apply so no last-applied annotation contains credentials.
The PAT value follows the upstream format: base64 of a non-empty email plus
colon plus PAT. That encoding is not encryption. Limit Secret access; use work
identity/expiry/rotation policy. Do not copy the lab Secret.

After work review, reconcile the rendered manifests through Flux (or apply them
for an explicitly authorized temporary trial), then verify:

```bash
kubectl --context '{{KUBE_CONTEXT}}' -n '{{NAMESPACE}}' rollout status deployment/azure-devops-mcp
scripts/kagent-verify-agent.sh --context '{{KUBE_CONTEXT}}' \
  --agent azure-devops-pr --ns '{{NAMESPACE}}' --controller-ns '{{CONTROLLER_NAMESPACE}}' --json
```

RemoteMCPServer Accepted and the bridge health check alone do not prove Azure
DevOps permissions. Perform a narrow repository read through the Agent first.

## 6. Create and independently verify one draft PR

```bash
scripts/kagent-a2a-invoke.sh --context '{{KUBE_CONTEXT}}' \
  --agent azure-devops-pr --ns '{{NAMESPACE}}' --controller-ns '{{CONTROLLER_NAMESPACE}}' \
  --timeout 180 --receipt-file /absolute/private/work-output/pr-a2a.json \
  --text 'In project {{ADO_PROJECT}}, repository {{ADO_REPOSITORY_ID}}, check active PRs for refs/heads/{{SOURCE_BRANCH}} to refs/heads/{{TARGET_BRANCH}}. If a matching PR exists report it. Otherwise create one draft PR using repo_pull_request_write action=create isDraft=true, title "docs: kagent MCP work demo". Read it back and report its ID, draft state, branch pair and web URL. Do not merge, autocomplete or add reviewers.'
```

Check Azure DevOps independently (UI or approved authenticated API): correct
repository/refs, draft=true, expected file diff, no autocomplete or unexpected
reviewers. Keep the raw receipt private: it may contain personal identities and
repository identifiers. Record tool-call evidence through existing kagent traces
where supported. Do not count an agent's statement alone as work-side proof.

Only `create` is exposed on the write tool; exact project/repo/source/target and
isDraft=true are checked by adapter code on every call. Other write tools and
extra effect fields are denied. This does not bypass branch policies, authorize
merges, or change Kubernetes/Azure permissions. Duplicate checking is an Agent
instruction, not transactional adapter deduplication. After ambiguous errors,
inspect existing PRs before retrying. Avoid concurrent creation requests.

## Disable writes / clean up

Render again with `--read-only`, review and reconcile. This removes the write tool
from bridge configuration and Agent tool selection. Restart the bridge after
credential rotation because env-backed credentials are read at startup. For
complete cleanup remove only these five named bundle resources through the same
delivery mechanism; separately revoke the demo PAT and remove its Secrets after
checking they are not shared. Abandon the draft PR/delete the source branch only
through your normal reviewed Azure DevOps process. Do not delete the namespace.

## Configuration inventory

`config.example.json`: NAMESPACE, MCP_IMAGE, ADO_ORGANIZATION, ADO_PROJECT,
ADO_REPOSITORY_ID, SOURCE_BRANCH, TARGET_BRANCH, MODEL_CONFIG_NAME.
Command placeholders: KUBE_CONTEXT, INTERNAL_REGISTRY, IMAGE_DIGEST,
CONTROLLER_NAMESPACE. No secret values belong in these files.

## References

- Official server/authentication: https://github.com/microsoft/azure-devops-mcp/blob/main/docs/GETTINGSTARTED.md
- Cloud/on-prem support: https://github.com/microsoft/azure-devops-mcp/blob/main/docs/FAQ.md
- Docker image save: https://docs.docker.com/reference/cli/docker/image/save/
- Docker image load: https://docs.docker.com/reference/cli/docker/image/load/
- Validated adapter snapshot: app/; sanitized evidence: evidence/
