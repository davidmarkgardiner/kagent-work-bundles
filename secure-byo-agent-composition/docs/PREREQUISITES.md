# Target inputs and installation boundaries

This reference describes the current builders. The work-agent procedure is in [WORK-AGENT-START-HERE.md](../WORK-AGENT-START-HERE.md). Private inputs and rendered output belong outside the extracted source tree.

## Profile construction inputs

`lab_resources.build_profiles(native_snapshot, settings)` reads selected native `AgentTemplate`, `ModelConfig`, and `Harness` specs. It produces equivalent profiles for `secure-byo-hosted` and `secure-byo-kro`. The snapshot remains private. Source object metadata and Secret values are not profile inputs.

Required settings include `runtimeImage` and `upstreamURL`. `runtimeImage` must use a reviewed SHA-256 manifest reference and contains the front door, composer, and matching CLI. Native agents retain the approved upstream ADK image.

The selected source object names default to the existing home-lab POC names. Override `templateName`, `modelName`, and `harnessName` for approved target objects. The source template must bind both reviewed content packages through immutable OCI digests.

`runtimeBridgeURL` identifies the protected gateway's runtime listener on port 8084. The dedicated native controller must compile its runtime control-plane endpoint to that origin, including the actor credential binding. Any additional Harness `workload` or `env` settings need explicit profile review.

Native CLI transport settings are `kagentBinary`, `apiURL`, `gatewayURL`, and `nativeUserID`. The deployment renderer gives each POC namespace a distinct native user ID. The front door creates new sessions itself and accepts no user-selected session or task IDs.

## Generated credentials and authorization references

The generated ModelConfig uses `secure-byo-mcp-token` key `token` and a per-POC gateway model endpoint. The generated MCP server uses that Secret's `Authorization` key and its separate MCP origin. Keeping distinct model and MCP origins avoids native credential-injection conflicts.

The front door mounts the platform-provisioned `secure-byo-model-token` Secret under `/credentials`. Its model proxy reads `/credentials/api-key`. Only the front door holds this upstream provider credential. The actor's approved model points to the protected proxy.

The approval record lives in the protected `demo-approval` ConfigMap for the default agent name. It binds caller account UIDs, request UID, Agent UID and spec hash, expiry, and the UIDs/spec hashes of AgentTemplate, Harness, ModelConfig, and RemoteMCPServer. The runtime reads those objects again on each decision and rejects changed references. The composer cannot publish approval.

`scripts/approval.py` is an explicit platform lab helper. `Active` mints a four-hour Kubernetes runtime token and publishes observed pins. MCP and model preparation can use the grant before readiness. Invocation requires all current native readiness conditions and the successful revision. The helper does not implement automatic token renewal or an Entra exchange.

## Platform baseline inputs

`build_baseline(settings)` emits the two protected namespaces, accounts, request-only owner roles, named runtime reads, TokenReview access, report-controller reads, and default-deny policies. Worker credentials and model credentials remain separately provisioned prerequisites.

Supply `workerPoolSpec` from the supported target release. The native API is `ate.dev/v1alpha1`, and the account is at `spec.template.serviceAccountName`. The builder sets the WorkerPool labels used by native actor placement. Confirm actual ready workers and matching placement labels before waiting for an Agent's golden snapshot.

The built-in network blueprint needs discovered `network.workerSelector`, `gatewaySelector`, `apiCIDRs`, `apiPorts`, and `nativePorts`. `workerExtraEgress` adds reviewed registry or snapshot paths. Workers receive no direct upstream model allow rule. The separate `network.py` renderer supplies the central-gateway and controller boundaries.

The renderers contain home-lab names and selectors, including the native controller namespace, model gateway, shared gateway, and trusted existing callers. Those names are source assumptions, not workplace discovery. Review and adapt them before target deployment. An incorrect selector can leave a controller unprotected even when the NetworkPolicy object is admitted.

## Shared routes and destination consent

With `centralRouting: true`, HTTPRoutes live in `secure-byo-gateway-system`. Each owner request creates its front-door Service and a namespace-local ReferenceGrant naming that Service. The grant allows configuration references from the protected route namespace. Runtime caller authorization remains separate.

The shared runtime GRPCRoute uses an independent backend Service in the native controller namespace and a destination-owner grant. Its Service declares h2c. The allowed RPC method list is in [AIRGAP-PREREQUISITES.md](../AIRGAP-PREREQUISITES.md#runtime-bridge-and-network-dependencies).

The dedicated controller compiles the runtime endpoint and actor credential binding together. The bridge exposes exact private task and memory RPC methods, forwards actor credentials unchanged, and denies management methods. Native actor authorization checks the requested session, actor UID, and atespace.

Cross-namespace objects have separate platform ownership. Namespaced ownerReferences do not span namespaces. Deleting an owner request retires its local resources and destination grant while shared gateway resources remain.

## Non-overlapping native controller ownership

The POC requires a dedicated native controller watching exactly `secure-byo-hosted` and `secure-byo-kro`. The existing controller retains its other owned namespaces and excludes those two. Native runtime defaults on the dedicated controller point to the runtime-only gateway. Front-door native CLI `apiURL` and `gatewayURL` point to the dedicated controller Service.

[scripts/controller_setup.py](../scripts/controller_setup.py) reads current objects and renders a private proposal by default. It needs the imported PyYAML wheel. Its optional `--apply` path changes and restarts the existing controller before starting the dedicated controller, so review the generated proposal before any use of that option.

Both controllers use the same approved native release. The dedicated controller uses database schema `secure_byo`; the existing controller retains its schema. [The schema migration](../prerequisites/schema.sql) must run under the database administrator's approved process before the dedicated controller starts. Review the `kagent_owner` and `kagent_readwrite` role mappings and default privileges. Existing schemas require inspection before migration, rather than automatic adoption.

The lab reuses reviewed database and identity references within the platform trust domain. This does not establish separate database or administrator isolation. The dedicated controller runs one replica with `Recreate` and leader election disabled to avoid the release's shared lease name. This POC setting does not establish high availability. Review target lease, database, credential, service selector, certificate, and service-account ownership before applying the proposal.

Do not silently narrow a workplace shared watch scope or install a competing controller. Obtain the platform owner's approved ownership split or use an isolated installation. The source renderer is preparation evidence; actual absence of overlapping reconciliation requires a live target check.

## Substrate credential namespace authority

The native credential provider separately maps an atespace to the Kubernetes namespaces from which it may obtain credentials. The two POC mappings each name only their own namespace. They do not grant one POC access to the other POC or to `kagent`.

[scripts/credential_policy.py](../scripts/credential_policy.py) renders a proposal by default, preserves existing mappings, and rejects a conflicting mapping. Its `--apply` option updates the shared provider ConfigMap and restarts its Deployment. Platform review of that shared prerequisite is separate from the owner's request authority.

## Home-lab discovery helper

`scripts/prepare_lab.py` requires explicit kubeconfig, context, output directory, front-door image digest. It discovers the selected native source objects, current worker image, API endpoints, acting platform identity, and Kubernetes public signing keys.

The helper also reads the selected model Secret and writes copies into `private-secrets.json` outside the bundle. This is authorized home-lab preparation. Workplace credentials must come from the workplace owner through its approved process. Do not treat a lab Secret export as a target credential decision.

## Evidence boundaries

The frontend runs as a non-root account with dropped capabilities, a read-only root filesystem, and a bounded writable `/tmp`. Its Kubernetes permissions cover token reviews and exact reads. Native Substrate workers need a separate reviewed privilege contract for sandbox lifecycle.

Admission evidence identifies the actual Kyverno rule and includes admitted controls. Network evidence distinguishes a rogue Pod, the actual worker, and the actor's atenet path. Native evidence identifies a fresh task and real tool calls and responses. Resource Ready conditions do not substitute for those receipts.

Entra compatibility, unattended renewal, target registry authentication, and workplace policy enforcement require their own successful receipts before corresponding deployment claims. Home-lab native content consumption used a warm Substrate cache. A cold import through an approved internal registry remains a separate target prerequisite and test.
