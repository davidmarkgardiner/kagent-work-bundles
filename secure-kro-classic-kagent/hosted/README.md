# Host the onboarding demo in AKS

The demo UI and Python backend can run in the same AKS cluster as the agent.
Use the included Dockerfile and renderer; no laptop backend or browser kubeconfig
is needed. This is a prepared deployment recipe, not evidence of a workplace rollout.
The home rehearsal used a local backend and real model calls.

```text
Browser --HTTPS--> existing Istio TLS Gateway
                    | demo UI host / --> VirtualService --> UI/backend Service :8766
                    | agent API host /exact/invoke/path
                    |                 --> VirtualService --> Agent Gateway :8080 --> kagent
UI/backend --Pod ServiceAccount--> Kubernetes API (one demo slot)
UI/backend --HTTPS + short-lived caller JWT--> agent API host --> same protected agent
kagent --> existing model Gateway --> approved LLM
```

Use separate UI and agent API hostnames. The frontend and backend share one origin;
there is no browser-to-cluster API connection and no CORS setup. The existing Istio
Gateway owns TLS and any organisation ingress gates. The agent's Gateway listener
continues to enforce its exact caller subject and JWT audience. An Entra edge gate
requiring a different backend token flow is a receiving-environment integration task;
this recipe does not perform that exchange.

## 1. Inspect the receiving environment

Read ../WORK-AGENT-HANDOFF.md and ../versions.lock.json. Discover the existing
controller images, CRDs, ready RGD, model configuration, Gateway listener policies,
Istio Gateway, DNS/TLS and delivery process. The reference is classic kagent 0.10.4,
KRO 0.9.4 and agentgateway 1.7.0. Do not upgrade controllers or replace shared policy
to make the demo pass. Stop on incompatibility and return the exact mismatch.

Use a dedicated demo agent namespace with no unrelated workloads. The UI account
can list Pods, Deployments, ReplicaSets and Services there, read the named graph
objects, mint only the caller/verifier tokens and manage one agent slot. A scoped
ValidatingAdmissionPolicy bounds owner creation and runtime Pod deletion because
RBAC cannot restrict CREATE by resource name. Kubernetes must serve this admission
API; verify the rendered policy's CEL type checks and its enforcement before launch.
Do not remove it to work around an unsupported cluster version.

The UI Pod has an API credential for management. The managed agent keeps its own
restricted runtime identity; these are separate permission boundaries. Neither the
browser nor the UI's Kubernetes Role receives model credentials. The UI Role has
no Secret read/list access. Hosted teardown therefore excludes native Secret metadata;
the operator must independently confirm any controller-created Secret cleanup.

## 2. Build the container

From the bundle root, build with approved, digest-pinned base images. The kubectl
image must match the receiving API's supported client skew and contain a runnable
binary at the supplied path. The Python base must include the organisation's trusted
CA roots for the agent HTTPS endpoint. Do not disable certificate verification.

```sh
docker build -f hosted/Dockerfile \
  --build-arg PYTHON_BASE='{{APPROVED_PYTHON_IMAGE_AT_SHA256_DIGEST}}' \
  --build-arg KUBECTL_IMAGE='{{APPROVED_KUBECTL_IMAGE_AT_SHA256_DIGEST}}' \
  --build-arg KUBECTL_BINARY_PATH='{{PATH_TO_BINARY_IN_KUBECTL_IMAGE}}' \
  -t '{{APPROVED_REGISTRY}}/dice-demo-ui:reviewed' .
```

Publish through the approved registry process and record the resulting image digest.
The Dockerfile copies only the runtime files. No kubeconfig, session key, model key,
private profile or build-directory contents are copied into the image. Check the
built image runs `python3` and `kubectl version --client` as UID 65532 before delivery.

## 3. Resolve private inputs and render

Copy values.example.json to a **private** working directory. Fill every placeholder:

- Exact UI HTTPS origin and distinct agent HTTPS invoke URL; existing TLS Gateway
  namespace/name, compatible agent Gateway Service name, audience and controller names.
- Approved image digest. List only the ConfigMaps actually referenced by the kagent
  controller's envFrom; use an empty list when none exist.
- Actual Istio ingress namespace/Pod labels and approved API/agent HTTPS egress CIDRs
  and destination ports. The backend must reach its own cluster's public agent URL
  through the approved ingress path. Validate this hairpin path from the Pod.
- The receiving CNI's pre/post-DNAT policy behavior and DNS topology. The template
  permits kube-system DNS on port 53; NodeLocal DNS or another namespace needs a
  reviewed adaptation. Service/API ports may differ from the endpoints after DNAT.
  Honour the receiving namespace mesh policy: sidecar/ambient interception may require
  additional reviewed control-plane, mTLS or HBONE paths. Do not disable the mesh
  to bypass the organisation's policy.
  Do not replace exact egress with an all-addresses rule to get a green test.

Provision `dice-demo-session` (or the configured name) in the UI namespace using the
approved secret delivery process. It needs a `session-key` entry: 32–256 characters
without whitespace. This is an operator capability to deploy/delete the one slot;
keep it private, out of Git, image layers and logs. The process mounts this Secret;
it has no Kubernetes Secret read permission. Retain the normal ingress access gate.

```sh
python3 hosted/render.py --values '{{PRIVATE_VALUES_JSON}}' --output '{{NEW_RENDER_DIRECTORY}}'
```

The renderer refuses unresolved placeholders, unpinned images and /0 egress. It emits
workload.json (Namespace, ServiceAccount, scoped RBAC, admission policy, hardened
Deployment, Service and NetworkPolicy) and virtualservices.json (two routes). Inspect
them before delivery. Ensure the approved namespaces already exist for server dry-run;
a dry-run Namespace in a List does not create it for subsequent objects.

```sh
kubectl --context '{{APPROVED_AKS_CONTEXT}}' apply --dry-run=server -f '{{RENDER_DIRECTORY}}/workload.json'
kubectl --context '{{APPROVED_AKS_CONTEXT}}' apply --dry-run=server -f '{{RENDER_DIRECTORY}}/virtualservices.json'
istioctl --context '{{APPROVED_AKS_CONTEXT}}' analyze -f '{{RENDER_DIRECTORY}}/virtualservices.json'
```

Deliver through the existing GitOps/platform process. Review cluster-scoped admission
objects and read-only CRD/RGD permissions with the platform owner. Establish RBAC,
admission enforcement, session Secret and network policy before exposing the backend.
Do not modify shared controllers, issuer, model catalog or listener authorization.

The UI route preserves Host and sends / to the UI Service. The agent route matches
only the configured invoke path and rewrites it to the classic caller path. Preserve
Authorization through all proxies. Both disable retries; the model route has a 150s
timeout and UI requests 180s. Confirm effective proxy configuration and any upstream
load balancer timeouts. See the [Istio VirtualService reference](https://istio.io/latest/docs/reference/config/networking/virtual-service/).
An existing route for either hostname must be reviewed instead of adding a competing
VirtualService. No native controller/Service bypass is an acceptable chat fallback.

## 4. Prove the demo in the receiving cluster

Open the UI HTTPS origin and enter the operator key. The backend checks the canonical
Host and Origin plus the session key. Forwarded headers cannot override that boundary.
The key stays in browser session storage; use a trusted operator browser and close the
session after presenting. `/healthz` reports only that the process serves requests,
not cluster access, model readiness or a security verdict.

1. Check platform: capture the actual pinned runtime/CRD/RGD and approved choices.
   Empty tools/skills are intentional in the initial model-only profile.
2. Deploy: watch actual owner, runtime, Golden Job and caller route. An LLM-generated
   Golden PONG and exact-owner receipt must pass; no fixture response counts.
3. Require positive caller PONG and rejection of missing JWT, wrong audience and
   wrong subject on the **same HTTPS VirtualService URL**. Admission dry-run negative
   tests under the UI ServiceAccount must reject a second owner name and unrelated
   Pod deletion; inspect effective RBAC as well.
4. Ask a short question. Save the native task ID and response digest. Verify the
   existing Gateway/model telemetry shows the model request. Namespace counts are
   backend Kubernetes reads supplied to the model, not an MCP tool call.
5. Test network enforcement independently from another identity/Pod and inspect all
   alternate routes/native APIs. JWT rejection alone is not isolation proof.
6. Tear down the connected UID. Require the owner and captured graph/runtime objects
   to disappear; independently check native Secrets with an operator account. Shared
   Gateway, ModelConfig and RGD must remain. Deploy again only as a separate action.

The demo uses one replica and Recreate deployment strategy because connection and
verification state are in memory. After a backend restart, use Connect existing agent
and verify caller access again; the agent itself is not automatically deleted.
This is a bounded operator demo, not a production multi-user provisioning service.

Return versions, rendered-object digests, image digest, actual HTTPS routes, admission
and RBAC checks, Golden receipt, native task ID/digest, JWT negatives, model telemetry,
teardown inventory and any unproven network/identity boundary. Keep private values
in the organisation's evidence store. Stop and report a failed gate; do not simulate
success or widen policy silently.
