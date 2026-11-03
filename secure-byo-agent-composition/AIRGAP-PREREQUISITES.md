# Air-gap artifact reference

The source ZIP is one replication input. Platform owners supply the following artifacts through the approved import process. Compatible existing installations can satisfy a prerequisite after discovery.

Complete [the human prerequisite sheet](HUMAN-PREREQUISITES.md) in the private target context. Copy the prior `agent-platform-four-crds` bundle and continue its HostedAgent operator using [the existing-operator instructions](docs/EXISTING-HOSTEDAGENT.md). Reuse compatible images, content and model wiring. Native-only prerequisites below do not override the prior no-Substrate path or authorize an upgrade.

## Version and artifact baseline

| Component | Pinned lab target | Required artifact or capability |
| --- | --- | --- |
| Kubernetes | v1.35.0 | Supported APIs, node architecture, and dedicated capacity |
| Native Kagent | 1.0.0-alpha17 | CRDs, controller, native ADK base, and matching CLI |
| Agent Substrate | 0.6.0-alpha3 | Controllers, WorkerPool images, credential provider, snapshot store, and sandbox assets |
| Kyverno | 1.17.1 | CRDs, running admission webhooks, and reporting access |
| KRO | 0.9.4 | Approved chart archive and rendered images |
| agentgateway | v1.5.0 | Controller and CRD charts, data-plane images, and h2c support |
| Gateway API | v1.6.2 experimental | Approved CRD manifests including GRPCRoute |
| Network provider | Target-specific | Actual NetworkPolicy enforcement and observed actor egress behavior |
| Front-door build base | Python 3.12 slim | Preloaded internal image with the digest in `versions.lock.json` |
| Diagnostic builds | Approved installed Go compiler | Complete offline inputs for the supplied diagnostic source |
| Controller-setup tooling | PyYAML 6.0.3 | Approved wheelhouse for `controller_setup.py` |
| Diagnostics | Target-approved binaries or images | Network and actor RPC probes with their build inputs |

[versions.lock.json](versions.lock.json) records chart digests and the Python base digest. The front-door builder requires that Python digest. An internal mirror that changes the manifest needs a reviewed lock update before this build helper accepts it.

The required Linux AMD64 Kagent alpha17 CLI SHA-256 is `01fb21bc46130dcffac5b5a720d903122563a4d926f4455cd8234c6112d338a3`. The lab's old alpha8 CLI failed with an unknown SessionService. A local binary called `kagent` is not a compatibility check.

## Imported artifact ledger

For every chart, manifest, binary, source archive, wheel, and image, record the following facts:

- Upstream project and exact source version or commit.
- Source checksum or digest and architecture.
- Approved transfer artifact and checksum.
- Internal destination and observed checksum or manifest digest.
- Owner, approval reference, and availability from the actual executor or node.

Render approved charts during connected preparation and enumerate every container image. Include init containers, chart hooks, gateway data planes, workers, credential providers, helpers, and diagnostic images. Check the complete list again after internal-registry substitutions. A chart archive does not include its images.

The upstream locations in the version lock identify imported source artifacts. They are not workplace download commands. Deployment and runtime must use approved internal locations.

[The input and artifact checklist](docs/INPUTS-AND-ARTIFACTS.md) separates known source pins from target values that still need discovery. The version lock is not an exhaustive image inventory. In particular, component versions do not identify every controller, chart hook, sidecar, and sandbox asset by digest.

## Image and controller inputs

The common front-door/composer image needs this source tree, the checked alpha17 CLI, and the approved Python base. [scripts/build.py](scripts/build.py) stages those inputs outside the source tree, verifies the CLI hash, requires the base locally, and builds with network disabled. Runtime Python uses the standard library and performs no package installation.

Native agents use the approved native ADK image. The dedicated controller uses the same pinned controller image and schema version as the existing native installation.

Controller configuration is a separate prerequisite. The dedicated controller watches exactly the two POC namespaces and compiles `runtimeDefaults.controlPlaneUrl` to the runtime-only gateway. The existing controller must exclude those namespaces while retaining all its other owned namespaces. Export and review both configurations before changes.

The dedicated controller uses a separate PostgreSQL schema, `secure_byo`, to keep its session lifecycle and garbage collection separate from the existing controller. [prerequisites/schema.sql](prerequisites/schema.sql) creates that schema and grants current and future table and sequence access to the lab's native database roles. A database administrator must review the role names and execute the approved migration before the new controller starts. The SQL intentionally fails if the schema already exists. Inspect its owner, contents, and grants instead of changing ownership or rerunning blindly.

Both controllers otherwise use the existing platform database and trusted identity. The POC's dedicated controller has one replica, a `Recreate` strategy, and leader election disabled because the upstream release uses the same lease name within one installation namespace. This is a local POC choice. High availability, separate installations, and controller lease isolation require a reviewed target design.

The Substrate Kubernetes credential provider must allow the two new atespaces to request credentials only from their matching namespaces. [scripts/credential_policy.py](scripts/credential_policy.py) preserves existing entries, adds `secure-byo-hosted -> secure-byo-hosted` and `secure-byo-kro -> secure-byo-kro`, and refuses conflicting authority. It renders a proposal by default. Its optional application path changes the shared ConfigMap and restarts the provider, so treat that as a platform-owned prerequisite.

Build diagnostic binaries only with the approved compiler and complete offline inputs. Import any third-party Go module dependencies as a vendor tree or through an approved internal module mirror. Disable public module access and automatic toolchain downloads. Record diagnostic binary hashes and image digests separately from the deployed runtime image.

## Native content and sandbox assets

Import both reviewed Skill and KnowledgeBase OCI packages into a worker-accessible internal registry. Preserve reviewed file bytes. Verify the final internal OCI manifest digests and use them in the protected profile. Do not rely on a previous node's content cache.

The successful home-lab native runs used content already present in the Substrate cache. They prove content consumption and tool behavior. They do not prove a cold worker can import those packages from a disconnected registry. The target acceptance must exercise that import with the actual internal registry and credential source.

Substrate also needs snapshot storage, DNS, certificate projection, registry credentials, kernel and device support, and its selected sandbox assets. Confirm the version-specific `runsc` source and checksum. Mirroring a worker container does not prove that every runtime asset is present.

Provider credentials belong to the platform. The native actor receives its scoped lab runtime credential. The front door mounts the private upstream model credential and proxies approved model requests. A copied lab Secret is not a workplace credential source.

## Runtime bridge and network dependencies

The native runtime bridge admits only these RPC methods:

| Service | Allowed methods |
| --- | --- |
| `kagent.runtime.v1.TaskStoreService` | `CreateTask`, `GetTask`, `UpdateTask`, `SettleTask`, `ListTasks` |
| `kagent.runtime.v1.MemoryService` | `AddSession`, `AddSessionBatch`, `Search` |

Do not match whole services. Other MemoryService methods use management authorization. The bridge preserves the Authorization header so the native controller can validate the actor and its session. A separate named backend Service declares `appProtocol: kubernetes.io/h2c`, and its destination owner supplies an exact ReferenceGrant.

The dedicated controller configures actor credentials for the runtime gateway origin. The actor's direct controller path stays denied. The gateway may reach the named controller backend. A route without the exact method list, or an allow rule admitting all atenet traffic directly to the controller, does not satisfy this design.

Kindnet alone does not enforce NetworkPolicy. The home lab adds policy-only kube-router. Work normally uses its approved network provider. Do not install another CNI or replace cluster networking to reproduce the lab's provider choice. Pair forbidden traffic probes with a working gateway path and test actual actor tunnel traffic.

## Identity, admission, and operational limits

The lab profile uses TokenReview with audience `secure-byo` and Kubernetes signing keys. The front-door account may create TokenReviews and read only the named approval, request, Agent, and four native dependencies. Owners have request-only RBAC. Namespace administrators who can create Pods under approved accounts remain inside that namespace's trust domain.

Entra needs a separate implemented identity adapter and target proof. Identity owners supply approved audiences and roles, federation, UAMI or blueprint/child bindings, token acquisition, renewal, and runtime reload. A Kubernetes token test does not establish Entra parity.

Kyverno needs active webhooks with the required operation and subresource coverage. A CLI command that evaluates zero rules is not admission evidence. Preserve existing Azure and workplace policies unless their owners approve a separate change.

The worker exception binds exact namespaces, controller identities, service account, image digests, and workload lineage. Qualifying trusted workers bypass the ordinary host namespace, hostPath, and capability restrictions. It does not attest their entire Pod specification. Record its owner, scope, expiry, and removal procedure. Ordinary Pods do not receive this exception.

The existing lab controller's user-authentication mode is insecure. The new POC's bridge and network rules restrict its actors, while existing trusted platform callers keep their paths. Replication must review that trusted-caller list and the target's authentication mode. This bundle does not prove that every existing cluster client is isolated.
