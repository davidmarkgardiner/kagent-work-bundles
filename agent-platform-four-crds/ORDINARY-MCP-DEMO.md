# Ordinary kagent onboarding with a fixed MCP capability

For backend-first private installation and local owner delivery, follow [AIRGAP-INSTALL.md](AIRGAP-INSTALL.md). The explicit `observe --delivery local` mode omits owner Flux references. With `--owner-manifest`, it uses server dry-run creates to prepare anticipated children, which requires the matching create authorization but persists nothing. Without that flag it captures fully live UID pins. The default Flux path below is unchanged.

This optional path adds the combined demo to the ordinary Deployment profile. It needs no Substrate. The original `package.py` default remains the documentation-only profile. An owner submits a **HostedAgent instance**, selecting reviewed Skill and KnowledgeBase releases and an approved runtime/model profile; the platform installs the CRDs and supplies the deployment details.

The lab uses ordinary controller-managed `kagent.dev/v1alpha2` Agents on kagent 0.7.13. Discover the exact workplace controller image, served Agent schema and runtime first. “kagent 10” is not a sufficient version pin. Use the existing workplace controller and approved model route. Do not install Substrate or change Azure Policy. If the target only serves the newer Harness/Substrate API, this ordinary controller profile is incompatible; report that gate rather than relabelling a standalone container as controller-managed onboarding.

## What the demonstration proves

A fresh synthetic documentation request loads `aks-known-issues`, reads its exact reference and the knowledge article, calls `get_demo_status` with no arguments, and uses the approved ModelConfig. The MCP backend performs a real Kubernetes GET of one immutable synthetic status ConfigMap. Its Role allows only that named GET. Its adapter accepts no arbitrary namespace, name, command, URL or write operation, and bounds requests/results/timeouts. This is a trusted-admin namespace demonstration, not hostile tenant isolation or a general ToolGrant service. The lab retains an existing namespace-wide same-namespace allow policy: unlabelled peers in that namespace can reach the synthetic service. A separate cross-namespace probe was blocked. NetworkPolicies are additive; inspect existing policies rather than claiming the new allow list overrides them.

`toolGrantRefs` stays empty. The additional capability belongs to one platform-approved profile, with ten typed backend UID/body pins. Discovery names, prompt instructions and tool filters do not enforce downstream permissions. The platform creates backend RBAC; the onboarding controller only reads these exact dependencies. A pin mismatch withdraws readiness; it does **not** revoke an already attached tool. Remove access through the platform's reviewed rollback when necessary.

## Prepare and render

First run `python3 -B verify.py`. Follow the existing README to render the baseline using a private, fully populated `workplace.json`. The examples below use private output paths held in shell variables; do not put workplace endpoints, credentials or target metadata in this public package. All generator commands create files only. The `bind` and `observe` stages perform named read-only Kubernetes GETs against the explicit context; none applies resources or publishes Git commits.

```sh
python3 package.py render --config "$WORK_CONFIG" --output "$BASE_RENDER"
python3 ordinary_demo.py mcp --config "$WORK_CONFIG" --render-root "$BASE_RENDER" \
  --evidence-code-file "$PRIVATE_SYNTHETIC_CODE_FILE" --output "$MCP_RENDER"
```

The synthetic code file contains 32 lowercase hex characters generated outside the agent prompt. It is a fixture proof, not a credential. Review `$MCP_RENDER/resources.yaml`, server-dry-run it, and deliver through approved GitOps after the normal workplace authorization. The configured controller image must support the bundled Python 3 code. The renderer uses normal worker requests; the lab's 5m Agent/MCP and 1m viewer/observer CPU requests are explicit capacity overrides, not workplace sizing guidance.

Before binding, verify actual downstream permissions using the backend Pod's service-account token: approved GET succeeds; other-name GET, list, Secret read, cross-namespace GET and dry-run create/patch/delete return 403. Check current RemoteMCPServer `Accepted` generation, exactly one discovered tool, the backend rollout, NetworkPolicy enforcement and output bounds. Token values must never enter evidence. A Role snapshot cannot rule out additional grants through other bindings, so keep these actual permission probes.

```sh
python3 ordinary_demo.py bind --config "$WORK_CONFIG" --render-root "$BASE_RENDER" \
  --context "$TARGET_CONTEXT" --mcp-manifest "$MCP_RENDER/resources.yaml" --output "$BIND_RENDER"
```

Review `backend-snapshot.json`, `profile.json`, `platform/resources.yaml`, and `hosted/resources.yaml`. The compiler checks the exact reviewed MCP code, startup hook, named-read Role and binding, then pins the live objects. The platform update preserves the old profile and adds `work-configmap-read-v1`; the separate request is `aks-platform-mcp-v1`. It refuses a cluster-wide CRD update that would remove another approved profile enum. The renderer compares the live hosted code/profile, Role and Deployment with the reviewed baseline and records four live UID/revision preconditions. Run this read-only check immediately before approved promotion:

```sh
python3 verify_preconditions.py --context "$TARGET_CONTEXT" --preconditions "$BIND_RENDER/preconditions.json"
```

A changed revision requires a new render/review; this preflight is not an atomic compare-and-swap across asynchronous GitOps delivery. Persistent manifests deliberately omit resourceVersion so later reconciliation continues. The platform output retains every baseline object and merges the four changes, avoiding accidental pruning of unrelated platform resources. Shared CRDs have pruning disabled (Flux documentation: https://fluxcd.io/flux/components/kustomize/kustomizations/#prune). Keep this in the existing platform reconciliation path; do not create competing managers for the same objects. Do not overwrite shared CRDs from a single namespace's profile configuration.

Verify legacy generated children remain unchanged. Commit platform and owner definitions to reviewed GitOps paths; deliver the platform update before the owner request. Give the new request its own Flux Kustomization and a GitRepository pinned to the reviewed **full commit**. A typical owner Kustomization has:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: '{{HOSTED_DELIVERY_NAME}}'
  namespace: '{{FLUX_NAMESPACE}}'
spec:
  interval: 30s
  timeout: 60s
  prune: true
  force: false
  path: '{{REVIEWED_HOSTED_PATH}}'
  sourceRef:
    kind: GitRepository
    name: '{{REVIEWED_GIT_SOURCE}}'
  targetNamespace: '{{AGENT_NAMESPACE}}'
  serviceAccountName: hosted-gitops
  healthChecks:
    - apiVersion: skills.platform.kagent.dev/v1alpha1
      kind: HostedAgent
      name: aks-platform-mcp-v1
      namespace: '{{AGENT_NAMESPACE}}'
```

Use the existing approved cross-namespace Flux service-account/impersonation pattern from the baseline. Record current Flux revision, HostedAgent Accepted/Ready, generated Agent Accepted/Ready, controller API availability, runtime Pod image ID and read-only mounted content hashes. This is separate from request acceptance.

## Trace the ordinary runtime

The installed lab translator appends global `OTEL_*` settings after per-Agent settings. A hash-pinned, opt-in `sitecustomize.py` hook enables tracing only for the new Agent; it does not modify shared Helm settings or roll old Agents. Before using it at work, verify the actual interpreter loads `sitecustomize`, that no existing hook would be shadowed, and that the installed runtime supports these tracing flags. Do not override an existing hook silently. Invalid endpoint configuration stops the new runtime with exit 78. Verify actual startup logs and received spans.

Verify the SDK's actual `service.name` and `service.namespace`; older Python runtimes report underscores. The viewer's mapping is explicit and exact. The controller may discard incoming `traceparent`, so that header is not evidence of propagation. Legacy `openai.chat` client reports own token accounting; `call_llm` bookkeeping is excluded. The configured gateway URL is used only to project an exact destination label, and is not exposed in viewer telemetry. No gateway server trace or per-request charge is invented when absent.

Create `$BASE_RENDER/ordinary-delivery.json` with the exact new owner's GitRepository and Kustomization names:

```json
{"declarations":"{{REVIEWED_GIT_SOURCE}}","flux":"{{HOSTED_DELIVERY_NAME}}"}
```

Then capture and render the observer:

```sh
python3 ordinary_demo.py observe --config "$WORK_CONFIG" --render-root "$BASE_RENDER" \
  --context "$TARGET_CONTEXT" --sdk-service-name "$SDK_SERVICE_NAME" \
  --sdk-service-namespace "$SDK_SERVICE_NAMESPACE" --output "$OBSERVE_RENDER"
```

The viewer has no invocation credentials or Kubernetes token. Only its observer sidecar receives a projected token with GET permission for 24 exact names; it has no list/watch/Secret/write permissions. It samples twice, checks current conditions and UID/body pins, expires observations after 15 seconds, and records only sampled transitions. A new reviewed plan is an intentional re-pin; all generated plan references include live UIDs. Do not present a late observer as having watched earlier creation transitions.

Review/deliver the observer and collector through GitOps, then port-forward the viewer on loopback:

```sh
kubectl --context "$TARGET_CONTEXT" -n "$AGENT_NAMESPACE" \
  port-forward --address=127.0.0.1 svc/ordinary-flow-dashboard 9445:8787
```

Open http://127.0.0.1:9445/#onboarding. The controller-managed Agent is invoked through the normal native front door or the bundled helper; the viewer observes externally initiated calls. The combined runner below creates one fresh synthetic request through that helper. Every output directory must be new.

```sh
python3 implementation/platform/skills-registry/hosted/combined_run.py \
  --context "$TARGET_CONTEXT" --controller-namespace "$KAGENT_NAMESPACE" \
  --profile "$BIND_RENDER/profile.json" --release "$BIND_RENDER/release.json" \
  --plan "$OBSERVE_RENDER/plan.json" --viewer http://127.0.0.1:9445 \
  --output-dir "$PRIVATE_RUN_DIR"
```

The runner verifies unchanged before/after dependencies and Pod/content identity, strict document results/citations, a fresh MCP execution ID and bounded result hash against a localhost-only backend audit, then exact SDK task/context/tool-call IDs and received model/gateway activity. Backend spans always use independent root traces: pooled MCP transports can retain old parent context. Only the accepted receipt's execution ID links backend completion to a request. No SDK spans are synthesized from A2A history. The audit endpoint retains the last eight operations, so read it promptly; eviction fails acceptance closed. Telemetry export failure does not replace the backend read result and is reported separately.

A passing runner writes `viewer-receipt.json`. Publish that metadata projection as the `receipt.json` key of a ConfigMap named `ordinary-flow-receipt` through the same approved delivery process. It contains IDs/hashes and reviewed call categories, not prompts, file arguments, contents or answers. The viewer shows it as current only when all dependency pins, profile/Agent hashes and freshness still match. Its skill/knowledge labels come from exact runner-correlated call IDs; unaccepted calls remain unattributed. A passing receipt is operator supplied and unsigned, not an attestation.

Run two distinct fresh contexts to test session reuse. Preserve failures and state why another run is needed. The lab retained a strict phrase-check failure caused by Markdown around `212`; the combined prompt now asks for the exact contiguous phrase `exit 212`. The original document checks remain strict.

## Roll back and add Substrate later

Preserve the original documentation-only Agent and profile. To withdraw this demo, first stop owner delivery and remove only its request/owned Agent through the reviewed GitOps process, then remove the separately platform-owned backend and observer resources when unused. Do not delete shared Skill/KnowledgeBase releases, the existing controller or shared CRDs. UID replacement or backend edits require a new reviewed profile/observer plan and acceptance.

When Azure Policy is cleared, discover the approved Substrate and kagent versions and implement a separate supported runtime profile. Prove skill/knowledge delivery, tool identity/restrictions, actor restore/checkpoint/suspend telemetry and rollback. This bundle does not implement a Substrate switch, a general tool catalog, dropdown/typeahead creator, external GitLab availability, or workplace deployment proof.
