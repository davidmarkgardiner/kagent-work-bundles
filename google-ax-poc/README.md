# Google AX POC and workplace use

**AX has a CLI, an API server, PostgreSQL state, and a Substrate execution
backend.** The CLI can run in an ordinary dev pod. The server and sandbox workers
still need an approved hosting cluster; connecting `kubectl` to a workload cluster
does not install them or create a Kubernetes-aware agent.

The 29 October 2026 POC used AX commit
`8440ae689d3314954b4f9f91d5b1460bdf5d6120`, Substrate v0.6.0 commit
`d3f2363590a11b2f50489971985ba033b4c9eff7`, Kubernetes v1.37.0, and a real
gVisor worker. It was a separate kind cluster, not an upgrade of the kagent lab.
See the [shared dev-pod and air-gap guide](../agent-runtime-workplace-guide/README.md)
for the recommended workplace topology and identity boundaries.

## What the POC proved

All **eight live upstream tests passed**, with no failures or skips:

| Check | Observed result |
|---|---|
| CLI | Version and automatic server tunnel |
| Workspace and Model | Apply, retrieve, describe, update, delete |
| Task lifecycle | Suspended creation, immutability, resume and matching Substrate state |
| Guest execution | Real sandbox commands, metadata endpoint and environment |
| Workspace setup | Fixture Git checkout, file overlays, skills directory and initialisation marker |
| Persistence | Workspace survived suspend/resume; a root-filesystem temporary file disappeared |
| Resource scoping | Task visibility respected the requested atespace filter |
| Task deletion | AX task, Substrate actor and per-task template were removed |

A retained Python task also produced `AX_POC_OK`. Its durable marker kept the
same SHA-256 through suspend/resume. The
[sanitized receipt](evidence/acceptance.json) records the checks.

This proves the orchestration and sandbox path. It does not prove a live LLM
call, MCP integration, enterprise authorization, kagent delegation, or offline
operation. The Git test used an image-baked fixture repository. Model CRUD was
configuration storage, not a provider invocation.

## Installed components

| Component | Function |
|---|---|
| `ax` | Submit and inspect AX resources; guest access with `ax ssh` |
| `ax-server` | AX gRPC API, task reconciliation and PostgreSQL-backed resource store |
| AX PostgreSQL | AX metadata and state; separate from Substrate's own database |
| AX task runner | Prepare workspace and supervise the configured command inside an actor |
| Substrate | API, controller, node agent, routing, certificate components and storage integration |
| gVisor WorkerPool | Execute actors using the versioned SandboxConfig runtime |

AX Task, Workspace and Model YAML is **not Kubernetes CRD YAML**. Apply it with
`ax`, not `kubectl`. Flux's ordinary Kubernetes apply path cannot reconcile it
without a separate integration. Substrate's Kubernetes resources remain a
different API.

## Use the CLI from a dev pod

The backend owner first installs and validates AX/Substrate in an approved
hosting cluster. Import the matching AX CLI, `kubectl`, CA trust and any required
kubeconfig authentication plugin into the dev image. Docker is not needed in the
client pod.

```bash
export KUBECONFIG="{{KUBECONFIG_PATH}}"
export AX_SYSTEM_NAMESPACE="{{AX_NAMESPACE}}"
ax --context "{{HOSTING_CONTEXT}}" --namespace "{{AX_NAMESPACE}}" get tasks
```

At this pin, AX can automatically start/reuse a `kubectl port-forward` to
`svc/ax-server:8080`. That needs Service/Pod discovery and port-forward permission.
Alternatively, an explicit loopback forward makes the route visible:

```bash
kubectl --context "{{HOSTING_CONTEXT}}" -n "{{AX_NAMESPACE}}" \
  port-forward --address 127.0.0.1 svc/ax-server 18080:8080
```

In another terminal:

```bash
ax --server http://127.0.0.1:18080 --context "{{HOSTING_CONTEXT}}" \
  --namespace "{{AX_NAMESPACE}}" -a "{{ATESPACE}}" get tasks
```

This is access to the **AX hosting cluster**. To investigate a separate workload
cluster, put the approved Kubernetes client/MCP integration in the task image or
execution service, provide its own scoped identity, and allow the necessary
runtime egress. The dev pod's kubeconfig is not automatically inherited by tasks.

### Guest access needs additional review

`ax ssh` is guest process/file access through Substrate, not an SSH server on the
target Kubernetes cluster. Tasks must be Running with `spec.debug: true`.
Besides AX gRPC access, the client needs a supported path to the atenet router
or worker. The pinned CLI has a direct plaintext worker path and a router path
that tries mTLS before a plaintext fallback.

The mTLS path lists ClusterTrustBundles and creates/reads/deletes
PodCertificateRequests for the configured AX service-account identity. Do not
grant broad certificate-issuance permissions merely to make the demo work.
Review identity issuance, allowed router clients and a fail-closed transport
design with the platform owner. AX resource reads and guest shell access are
separate acceptance gates. See the shared guide's
[transport section](../agent-runtime-workplace-guide/README.md#transport-and-identity-require-a-workplace-design).

## Reproduce a bounded task after backend acceptance

The [portable demo](demo.yaml) uses files only, so no Git, model, or MCP network
dependency is needed. It is a template for the approved backend, not an installer.
The backend must have an approved digest-pinned default runner image containing
Python 3, or the owner must add that image reference to `spec.image`.

```bash
ax --context "{{HOSTING_CONTEXT}}" --namespace "{{AX_NAMESPACE}}" \
  -a "{{ATESPACE}}" apply -f demo.yaml
ax --context "{{HOSTING_CONTEXT}}" --namespace "{{AX_NAMESPACE}}" \
  -a "{{ATESPACE}}" resume task ax-reference-demo
ax --context "{{HOSTING_CONTEXT}}" --namespace "{{AX_NAMESPACE}}" \
  -a "{{ATESPACE}}" describe task ax-reference-demo
```

After approved guest access is available, inspect
`/workspace/task-result.json` using `ax ssh`. A newly created task starts Suspended
at this pin. Ready means the runner/workspace is available; the runner stays up
after the command exits. Check output and explicit completion evidence rather
than treating Running as command success.

Suspend/resume preserves the workspace volume in the demonstrated profile and
cold-boots the root filesystem. This is not proof of RAM continuation. The live
deletion test checked task/actor/template removal, not object-store garbage
collection or complete platform teardown.

## Air-gap import requirements

Import the AX CLI and the complete backend dependency set, not just two AX
images. The [observed runtime image inventory](runtime-images.json) records AX,
Substrate, database, certificate and bundled observability images from the lab.
It includes the actor runner, which is not an ordinary Kubernetes Pod image.
This is a lab-profile inventory, not a universal platform bill of materials.

The `{{INTERNAL_REGISTRY}}` references are destinations for approved imports.
Lab-built images are not publicly available at those paths or from this folder.
Build from the pinned sources in the approved connected pipeline, export/import
the OCI content, verify the imported digests, and rewrite manifests. Review
optional observability components with the selected platform profile; do not
silently omit a dependency from an installed profile.

Substrate additionally needs the separately imported gVisor archive and its
helpers. [runtime-assets.json](runtime-assets.json) records both architecture
references from the pinned SandboxConfig; only amd64 was exercised in this POC.
Configure supported internal asset resolution and prove a fresh-cache fetch.
An imported worker image or a cached `runsc` on one old node does not establish
air-gap readiness.

Prebuilding the complete runtime images avoids a compiler/build daemon in the
dev pod. Rebuilding internally requires the complete Go module graph, toolchain,
Buildx, base images, package inputs, and Rust/Cargo dependencies for the Envoy
component. The lab used Go 1.27.3; missing Buildx was resolved with an isolated,
checksum-verified v0.38.1 installation. The successful lab setup had internet
access and must not be run unchanged inside an air gap.

## Workplace acceptance and configuration

Platform owners must approve the required Kubernetes APIs, certificate
projections/signers, node permissions, admission policies, storage and runtime
support. A dev pod's access to a remote Kubernetes API cannot enable unsupported
managed-control-plane features or satisfy blocked host-level sandbox privileges.
The lab is not AKS or workplace proof. Keep the existing kagent installation
separate until version and ownership compatibility are established.

Use the shared guide's clean-cache offline gate before calling this air-gap
ready. The upstream kind setup script is a connected bootstrap/test helper,
not a workplace upgrade path: it can reset AX PostgreSQL data during deployment.

| Placeholder | Owner supplies |
|---|---|
| `{{KUBECONFIG_PATH}}` | Approved credential file inside the dev pod |
| `{{HOSTING_CONTEXT}}` | Explicit AX/Substrate hosting cluster context |
| `{{AX_NAMESPACE}}` | Approved AX namespace; also set AX_SYSTEM_NAMESPACE for this CLI's guest path |
| `{{ATESPACE}}` | Approved Substrate/AX scope; not a substitute for caller authorization |
| `{{INTERNAL_REGISTRY}}` | Approved mirror registry/repository prefix after artifact import |

## Pinned sources

- [AX README](https://github.com/google/ax/blob/8440ae689d3314954b4f9f91d5b1460bdf5d6120/README.md)
- [Live tests](https://github.com/google/ax/blob/8440ae689d3314954b4f9f91d5b1460bdf5d6120/test/e2e/e2e_test.go)
- [Setup script](https://github.com/google/ax/blob/8440ae689d3314954b4f9f91d5b1460bdf5d6120/hack/setup-e2e-kind.sh)
- [CLI routing](https://github.com/google/ax/blob/8440ae689d3314954b4f9f91d5b1460bdf5d6120/cmd/ax/main.go)
- [Router certificate helper](https://github.com/google/ax/blob/8440ae689d3314954b4f9f91d5b1460bdf5d6120/internal/tunnel/router_tls.go)
