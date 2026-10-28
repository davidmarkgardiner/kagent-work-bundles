# Deploy the native skills and knowledge POC

Get one documentation agent working on the existing cluster, then demonstrate bringing an owner-authored agent definition and content through the same flow.

## What has been proved

The saved Proxmox lab receipts record **kagent 1.0.0-alpha17**, **API `api.kagent.dev/v1alpha3`** and **Substrate 0.6.0-alpha3**. The generated Agent loaded both the skill and knowledge package, read their exact files and passed GoldenScenario. The native OTel follow-up recorded three model calls, two `load_skill` calls and four `load_skill_resource` calls.

The native implementation and receipts are included under [implementation/platform/skills-registry/native/](implementation/platform/skills-registry/native/). This is recorded lab proof, not a claim that the workplace deployment has already passed. `v1alpha3` is the API version, not the release name.

## Choose the namespace

**Choose any namespace the work account is permitted to use.** There is no requirement to call it `kagent`, `agent-platform` or `skills-demo`. Using a namespace with an existing suitable Harness and ModelConfig is the fastest route.

The native Agent, AgentTemplate, Harness, ModelConfig, custom requests and Flux GitRepository references must resolve in the chosen namespace. Reuse or create suitable namespace-local dependencies through the existing platform flow. The existing controller must watch that namespace; its own deployment can remain elsewhere. CRD definitions are cluster-scoped, so check existing definitions before applying them.

Set the same namespace in renderer arguments, request examples, source objects, service accounts and the acceptance runner. Lab examples use `kagent`; replace their namespaces and lab-only pins in private copies.

## Build or import only these inputs

- Reuse the existing kagent/Substrate platform and model route. Import the exact native Go ADK image from [build/kagent-1.0-target.json](build/kagent-1.0-target.json) only if it is missing internally.
- Build one Python helper image with [build/Dockerfile.helpers](build/Dockerfile.helpers), or reuse a suitable approved Python 3.12-compatible image. Both adapters use it; their code is mounted from generated ConfigMaps.
- Publish **two data-only OCI content images**, one Skill and one KnowledgeBase. Use the included native `publish.py` and `artifacts.py`. These package reviewed Markdown and release proofs; they need no executable, OS base image or Docker build. Copy the layouts to the internal registry with ORAS and record their manifest digests.
- Have Python, Git, kubectl, Helm as needed, and ORAS available. A new collector or dashboard is optional for this first POC. The lab content publisher emits Linux/AMD64 image metadata; use matching workers for the first reproduction.

## Run the POC

1. Verify the installed release/API and choose the namespace, existing model and suitable Harness. Preserve shared platform resources.
2. Export the bundled sample content with `package.py content --output '{{NEW_CONTENT_SEED_DIRECTORY}}'`. Place it in a small internal Git source reachable by Flux. Pin the real content commit. Use native `examples/requests.yaml` as a template and recompute release/source/profile hashes for the target. Its lab fixture commits are examples, not downloadable sources.
3. Publish each reviewed release from its exact Git commit:
   ```bash
   python3 implementation/platform/skills-registry/native/publish.py \
     --git '{{CONTENT_GIT_CHECKOUT}}' --release '{{REVIEWED_RELEASE_JSON}}' \
     --layout '{{NEW_OCI_LAYOUT_DIRECTORY}}'
   oras cp --from-oci-layout '{{NEW_OCI_LAYOUT_DIRECTORY}}:reviewed' \
     '{{INTERNAL_CONTENT_REPOSITORY}}:{{POC_TAG}}'
   ```
   Put the returned digest, complete release spec hash, Flux source spec hash and current Harness/ModelConfig spec hashes into a private copy of `native/examples/profile.example.json`. Configure private registry pulls through the existing runtime.
4. Render the native platform:
   ```bash
   python3 implementation/platform/skills-registry/native/resources.py \
     --profile '{{PRIVATE_PROFILE_JSON}}' --namespace '{{POC_NAMESPACE}}' \
     > '{{PRIVATE_PLATFORM_JSON}}'
   ```
   In the generated Deployments, select the internal helper image, remove the inherited lab control-plane selector/toleration unless actually required, and set `SOURCE_CONTROLLER_ORIGIN` to the real Flux source-controller origin. Verify API/source connectivity. The sample CI recipe's public package downloads are not required for this path.
5. Review the generated changes, then install the four CRDs and two adapters through the authorized cluster process. Apply the pinned source and Skill/KnowledgeBase releases, wait for content readiness, then submit HostedAgent and the native GoldenScenario. Use the native renderer, not the legacy `package.py render` or `private_install.py`.
6. Run the native `run_golden.py` with the chosen `--namespace`, matching CLI/config and a fresh evidence directory. Start from `examples/golden-exact-citation.yaml`; update its namespace and HostedAgent spec pin. Its fresh-session receipt must pass and show exact skill/knowledge file reads. Save the private deployment parameters and cleanup commands.

The first milestone is complete when both adapters run, the releases and generated Agent are Ready, and a fresh native session reads both packages and cites the knowledge source. Attach no operational Azure/Kubernetes tools. The trusted-admin lab runtime still advertises file-write tools; observed read-only calls are not a sandbox-isolation claim.

Defer the dashboard, automatic pipeline promotion, fleet rollout, recovery exercises and BYO-agent onboarding until this passes. For the next milestone, keep the working platform and submit a new owner-authored agent definition with its reviewed skill and knowledge releases.
