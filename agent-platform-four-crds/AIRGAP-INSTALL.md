# Legacy kagent 0.7 air-gap installation

**For the requested kagent 1.0.0-alpha17 target, use [KAGENT-1.0-WORK-AGENT-PROMPT.md](KAGENT-1.0-WORK-AGENT-PROMPT.md) and [build/README.md](build/README.md).** The procedure below requires the legacy renderer and ordinary Agent runtime. It does not install the native 1.0 profile.

Prepare the platform once, then use Copilot or Codex in VS Code to draft the local owner definition. An authorized operator submits that file with `kubectl apply`. The onboarding controller creates the native Agent, and the existing kagent controller deploys it. Invoke through the native API or UI and inspect received OTel activity in the private panel.

This guide targets ordinary `kagent.dev/v1alpha2` Agents. It requires no Substrate or Azure Policy change. It is a workplace installation procedure, not a report that a workplace deployment has passed.

## 1. Establish the target and trust boundary

Use a dedicated, platform-controlled namespace. Reuse the existing kagent controller, frontend, model gateway, internal model route, and Flux source-controller. Do not install a second kagent controller or modify shared defaults to fit the example.

Inspect the actual controller version, served Agent schema, runtime image composition, Service labels and ports, CNI enforcement, and admission policies. The previous lab used kagent 0.7.13 and Kubernetes 1.31.14. A statement such as "kagent 10" does not identify a compatible API or runtime.

Before applying anything, verify that this target supports `deployment.securityContext`, `podSecurityContext`, read-only projected ConfigMaps, resources, and the per-Agent tracing hook. An unknown field may be pruned instead of enforced. Inspect actual Pods after reconciliation. If the target only supports a Substrate-required API, stop this installation path and report that incompatibility.

Separate these identities.

- The platform installer manages the CRDs, controllers, approved profiles, networking, admission and content releases.
- The owner author drafts a local file without cluster credentials. An optional owner submitter can create and read only namespaced HostedAgent resources through a separately approved identity.
- The onboarding controller creates fixed-profile native Agent resources. It has no RoleBinding creation or Secret-read permission.
- The runtime agent has no operational Kubernetes RoleBinding. The existing controller may still inject a model credential and an audience-specific kagent token. Inspect both the mounted token audiences and effective access.
- The MCP backend can GET only the single synthetic status ConfigMap. The viewer gets no Kubernetes token. Only its separate observer has named read access.

An identity allowed to create arbitrary Pods, native Agents, RoleBindings, ServiceAccounts, or controller ConfigMaps can bypass this owner contract. Do not give those rights to the owner or coding assistant. RBAC cannot restrict a `create` verb to a single resource name. Use the compiler's approved owner-name constraint and the workplace admission rules as applicable. This is not a hostile multi-tenant sandbox.

## 2. Build and import all image inputs

Follow [build/README.md](build/README.md). Build helper, collector and exact native runtime images from reviewed internal inputs. The bundle includes Dockerfiles for those builds, not their base images, binaries, wheels, or every upstream dependency.

Inventory the existing kagent controller, UI, gateway, model services, Flux and any init containers too. Every required image and dependency must already be accessible through approved internal services. Record source commits, architecture, manifest digests, SBOMs and vulnerability decisions. Use the private CA trust process. Do not bypass TLS verification.

Verify the nodes can authenticate to the approved internal registry using the existing platform configuration. This renderer does not create registry credentials or distribute pull Secrets. If the target requires additional pull-secret wiring, stop and have the platform team add and review it before deployment. Do not grant the runtime image-pull credentials as an application tool credential.

Lock the ordinary controller's composed runtime tag to the approved digest through registry immutability or existing admission enforcement. Check the actual runtime `imageID` after deployment. The Declarative API's `imageRegistry` is a prefix, not an arbitrary image override.

Public documentation URLs inside reviewed content are citations. They need not be fetched by the agent. The model, Git content, image registry, DNS, Kubernetes API and telemetry endpoints used at runtime must all be internal approved routes.

## 3. Prepare private configuration and render locally

Run the package verifier with the approved offline Python environment.

```bash
python3 -B verify.py
```

Copy `config.example.json` and `private_install.example.json` outside the public package. Replace all placeholders using target evidence. The base config still describes the internal Git content source because skill ingestion uses source-controller artifacts. Owner delivery does not need a Flux Kustomization.

The private config names the approved internal registry, helper and collector images at digests, the expected controller-composed runtime reference, the reserved demo owner name, and exact network peers. API and DNS addresses depend on the target CNI and service NAT behavior. Do not copy lab addresses. Configure DNS over UDP and TCP. Do not widen an allow list to `0.0.0.0/0` when a call fails.

```bash
export PRIVATE_CONFIG='/absolute/private/path/private_install.json'
export PRIVATE_RENDER='/absolute/private/path/new-private-render'
export WORK_CONFIG='/absolute/private/path/workplace.json'
export TARGET_CONTEXT='{{APPROVED_KUBE_CONTEXT}}'
export APP_NAMESPACE='{{DEDICATED_APPLICATION_NAMESPACE}}'
export KAGENT_NAMESPACE='{{EXISTING_KAGENT_NAMESPACE}}'
python3 -B private_install.py --config "$PRIVATE_CONFIG" --output "$PRIVATE_RENDER"
```

Render output is reviewable local YAML. Rendering performs no deployment. Keep target configuration and output outside the public repo. Review any offline audit and unresolved target gates before proceeding.

## 4. Install the backend in order

Use the target's existing platform authorization. Do not apply the complete directory recursively. Custom resource dry-runs must follow CRD establishment.

For a new dedicated namespace, review and install the namespace policy and resource budgets first.

```bash
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$PRIVATE_RENDER/bootstrap/00-namespace.yaml"
kubectl --context "$TARGET_CONTEXT" apply \
  -f "$PRIVATE_RENDER/bootstrap/00-namespace.yaml"
```

This private namespace uses Restricted Pod Security admission, default network denial, resource budgets and LimitRange settings. Review existing admission rules before combining them. Do not relabel a shared namespace or change its quotas to make the demo fit.

Review and install the platform CRDs, fixed-profile adapters and their namespaced RBAC.

```bash
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$PRIVATE_RENDER/bootstrap/10-platform.yaml"
kubectl --context "$TARGET_CONTEXT" apply \
  -f "$PRIVATE_RENDER/bootstrap/10-platform.yaml"
kubectl --context "$TARGET_CONTEXT" wait --for=condition=Established --timeout=120s \
  crd/skills.skills.platform.kagent.dev \
  crd/knowledgebases.skills.platform.kagent.dev \
  crd/hostedagents.skills.platform.kagent.dev \
  crd/goldenscenarios.skills.platform.kagent.dev
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/skill-adapter --timeout=180s
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/hosted-agent-adapter --timeout=180s
```

The four CRDs are cluster-scoped shared definitions. Review existing profile enums and schema ownership before changing an already installed CRD. Stop if the generated set would remove another approved profile. Do not use force ownership or delete CRDs as a repair.

Install the reviewed internal content source and releases next. Provision referenced Git credentials through the existing secret-management process, not from a file in this bundle.

```bash
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$PRIVATE_RENDER/bootstrap/20-content.yaml"
kubectl --context "$TARGET_CONTEXT" apply \
  -f "$PRIVATE_RENDER/bootstrap/20-content.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Ready=True --timeout=180s \
  gitrepositories.source.toolkit.fluxcd.io/reviewed-content-v1
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Ready=True --timeout=180s \
  skills.skills.platform.kagent.dev/aks-known-issues-v1 \
  knowledgebases.skills.platform.kagent.dev/aks-bootstrap-v1
```

Install the fixed MCP backend. It performs no operational remediation.

```bash
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$PRIVATE_RENDER/bootstrap/30-mcp.yaml"
kubectl --context "$TARGET_CONTEXT" apply \
  -f "$PRIVATE_RENDER/bootstrap/30-mcp.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/onboarding-status-mcp --timeout=180s
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Accepted=True --timeout=180s \
  remotemcpservers.kagent.dev/onboarding-status-mcp
```

Before approving the capability, use its actual service-account identity to prove the allowed GET succeeds. Prove other-name GET, ConfigMap list, Secret read, cross-namespace read, and dry-run create, patch and delete fail. Check the discovered tool list contains only `get_demo_status`. A Role definition alone does not rule out additional bindings. Do not write token values into evidence.

## 5. Bind the approved capability and prepare the panel

The platform binding reads live named dependencies and produces a second approved runtime profile. It does not apply it. The private render contains the base render used in this step.

```bash
export BASE_RENDER="$PRIVATE_RENDER/base"
export BIND_RENDER='/absolute/private/path/new-bind-render'
python3 -B ordinary_demo.py bind --config "$WORK_CONFIG" \
  --render-root "$BASE_RENDER" --context "$TARGET_CONTEXT" \
  --mcp-manifest "$PRIVATE_RENDER/bootstrap/30-mcp.yaml" --output "$BIND_RENDER"
python3 -B verify_preconditions.py --context "$TARGET_CONTEXT" \
  --preconditions "$BIND_RENDER/preconditions.json"
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$BIND_RENDER/platform/resources.yaml"
kubectl --context "$TARGET_CONTEXT" apply -f "$BIND_RENDER/platform/resources.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/hosted-agent-adapter --timeout=180s
```

Keep one delivery manager for these platform objects. Do not manually compete with an active platform Flux Kustomization. Preserve existing profiles and agents. The revision preflight is not an atomic transaction with apply.

Verify the actual SDK resource identity reported by the installed native runtime. The tested older Python SDK replaces hyphens with underscores, but discover the exact behavior on the target. Set both values explicitly.

```bash
export SDK_SERVICE_NAME='{{VERIFIED_SDK_SERVICE_NAME}}'
export SDK_SERVICE_NAMESPACE='{{VERIFIED_SDK_SERVICE_NAMESPACE}}'
export PRIVATE_COLLECTOR_IMAGE='{{INTERNAL_COLLECTOR_IMAGE_AT_SHA256}}'
export OBSERVE_RENDER='/absolute/private/path/new-observer-render'
python3 -B ordinary_demo.py observe --config "$WORK_CONFIG" \
  --render-root "$BASE_RENDER" --context "$TARGET_CONTEXT" --delivery local \
  --owner-manifest "$BIND_RENDER/hosted/resources.yaml" \
  --collector-image "$PRIVATE_COLLECTOR_IMAGE" \
  --sdk-service-name "$SDK_SERVICE_NAME" --sdk-service-namespace "$SDK_SERVICE_NAMESPACE" \
  --output "$OBSERVE_RENDER"
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$OBSERVE_RENDER/resources.yaml"
kubectl --context "$TARGET_CONTEXT" apply -f "$OBSERVE_RENDER/resources.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/ordinary-flow-dashboard --timeout=180s
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/ordinary-flow-collector --timeout=180s
```

The local owner mode does not invent a Flux revision. Precreation rendering performs server dry-run creates for the exact owner and anticipated children, so the platform renderer needs the corresponding create authorization even though nothing is persisted. Existing names or admission failures stop the render. Expected hashes come from admitted responses rather than guesses about API defaults.

For anticipated children, the observer watches exact names and expected body hashes, then latches the first observed UID. Existing backend/content resources retain their live UID pins. Treat first observation as an operator-controlled trust step. A container restart within the same Pod retains the snapshot in its `emptyDir`. Pod replacement loses that state. Before presenting invocation or running acceptance, capture and install a fully live-UID plan as described below. Do not leave a precreation trust plan as the permanent observer configuration.

Use the loopback port-forwards in [PRESENTER-WALKTHROUGH.md](PRESENTER-WALKTHROUGH.md). Keep the viewer and frontend as internal ClusterIP services. Do not create a public LoadBalancer, NodePort, ingress, or unauthenticated externally reachable telemetry endpoint. For shared workplace access, use the existing approved authentication and authorization front door.

## 6. Draft, apply and invoke the owner definition

Follow [VSCODE-AGENT-AUTHORING.md](VSCODE-AGENT-AUTHORING.md). Copilot or Codex can refine the reviewed example's purpose and instructions. Images, resource limits, service accounts, tool permissions and content pins remain platform-owned.

Follow the local submission, readiness and prompt steps in [PRESENTER-WALKTHROUGH.md](PRESENTER-WALKTHROUGH.md). The supported fixed demo name is `aks-platform-mcp-v1`. A general agent catalog or conversational deployment service is outside this implementation.

After the owner and native Agent become Ready, capture live UIDs without `--owner-manifest`. Review and install this final observer before invocation. The new plan rejects replacement independently of an observer Pod's old state.

```bash
export LIVE_OBSERVE_RENDER='/absolute/private/path/new-live-observer-render'
python3 -B ordinary_demo.py observe --config "$WORK_CONFIG" \
  --render-root "$BASE_RENDER" --context "$TARGET_CONTEXT" --delivery local \
  --collector-image "$PRIVATE_COLLECTOR_IMAGE" \
  --sdk-service-name "$SDK_SERVICE_NAME" --sdk-service-namespace "$SDK_SERVICE_NAMESPACE" \
  --output "$LIVE_OBSERVE_RENDER"
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$LIVE_OBSERVE_RENDER/resources.yaml"
kubectl --context "$TARGET_CONTEXT" apply -f "$LIVE_OBSERVE_RENDER/resources.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status deployment/ordinary-flow-dashboard --timeout=180s
export OBSERVE_RENDER="$LIVE_OBSERVE_RENDER"
```

This observer rollout starts a new in-memory display history. Do not describe it as retaining earlier creation transitions. The initial panel showed creation while it ran; the final plan provides the stable invocation view and acceptance pins.

Use native A2A first for repeatable proof. Rehearse the browser UI separately. New frontend requests must not inherit labels or MCP completion claims from an older passing receipt. The verified tool classification and independent backend correlation still require the acceptance runner's matching evidence.

## 7. Complete target acceptance before calling it ready

Record these actual target results privately.

- All backend Pods are Available and all releases use the reviewed source and content hashes.
- Every effective container and init container has CPU, memory and ephemeral-storage requests and limits. All are non-root, drop capabilities, deny privilege escalation, use RuntimeDefault seccomp and read-only roots with only bounded reviewed writable volumes. No host namespaces, hostPath, privileged container or arbitrary native skill initializer appears.
- All effective images, including controller-generated runtime and init images, are approved internal builds. Actual `imageID` matches the approved digest inventory.
- Owner and runtime identities fail unauthorized Secret, binding, pod, workload and cross-namespace operations. Actual MCP permission negatives pass. No wildcard, bind, escalate, impersonate, token-creation or RoleBinding creation capability reaches an owner or runtime.
- Default-deny policy is enforced by the actual CNI. Only the documented API, DNS, content, model, controller, MCP and telemetry flows succeed. Test a disallowed internal peer and external egress. Existing policies are additive and can widen access; reject broad existing permits rather than assuming a new deny policy overrides them.
- No credentials or raw content leak through viewer JSON, traces, logs or public files. The viewer invocation route returns 403. The telemetry receiver is an internal trusted component, not an authenticated multi-tenant ingestion service.
- A fresh local request becomes Accepted and Ready. A fresh native invocation reads both reviewed documents, calls the fixed tool and returns citations and synthetic evidence. Received SDK spans and independently audited MCP evidence match that request.
- A clean isolated builder and fresh target run need no public downloads, dependency resolver access, public CDN, or cached public image. Preserve firewall or network-denial evidence.

If any field is dropped, effective permissions are wider, the runtime cannot run with the security settings, or telemetry is missing, keep that gate failed. Do not weaken admission, limits, image policy or network rules to obtain a presentation result.

## Security references

The implementation and target acceptance follow these upstream references. Use documentation for the target Kubernetes version when checking exact availability.

- https://kubernetes.io/docs/concepts/security/rbac-good-practices/
- https://kubernetes.io/docs/concepts/security/pod-security-standards/
- https://kubernetes.io/docs/concepts/services-networking/network-policies/

Source generation, static audits and offline tests do not establish workplace security, CNI enforcement or air-gap closure. Those remain target acceptance results until independently observed.
