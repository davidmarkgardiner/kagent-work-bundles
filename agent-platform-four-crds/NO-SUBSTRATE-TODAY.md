# Finish the CRD POC today without Substrate

Resume from the four CRDs already established and the images already built. Use the standalone Job implementation in `standalone/`. Do not install Substrate, create a Harness or WorkerPool, configure snapshots, upgrade kagent or return to the old `v1alpha2` ordinary-Agent path.

## Current blocker: content has not been published or materialized

Start with [CONTENT-BOOTSTRAP-SHEET.md](CONTENT-BOOTSTRAP-SHEET.md). Publish the provided sample into an approved internal Git source, pin the actual commit, run the content-only adapter, and wait for both real releases and immutable ConfigMaps. Only then capture snapshots and prepare the Job. The sheet assigns the bootstrap work and exact missing-input handback; a bundled sample or local test fixture is not a workplace release.

## What the feedback establishes

| Concern | Resolution for today's POC |
| --- | --- |
| Native Harness requires a WorkerPool and snapshots | Confirmed against kagent alpha8's upstream schema. Leave the native generated-Agent route unused. |
| No namespace-local Harness or WorkerPool | Neither is needed by the standalone Job. |
| No ModelConfig in the desired namespace | Inspect the existing resolved Qwen configuration to identify the real model route and its authentication. Supply that route explicitly to the Job. It does not resolve a native ModelConfig reference. |
| alpha8 cluster versus alpha17 lab bundle | Do not assume API-family compatibility. This path uses the four custom CRDs, content ConfigMaps and Kubernetes `batch/v1` Job rather than either native Agent/Harness compiler. |
| Report lists a Substrate version, while the operator says it is absent | A reported chart/dependency version is not a usable WorkerPool. Record actual state if useful, but do not make installation or diagnosis of Substrate a prerequisite for this Job. |

## Execute in this order

1. Keep the established CRDs and existing images. Choose a permitted POC namespace. Prefer one where image-pull credentials and model authentication already work, so namespace migration does not add setup. Inspect existing CRD enum values and request specs before changes. Use the additive guarded patches emitted by `standalone/prepare.py`; do not replace the four installed CRDs with an unrelated historical schema. Create new standalone HostedAgent/GoldenScenario names if earlier native requests already exist, because their specs are immutable.
2. Reuse the compatible Python 3.12 helper image at its approved internal digest. There is no Go ADK binary or new Python dependency installation in this path. Existing native runtime and OCI content images can remain for later work. The Job reads the verified ConfigMaps, so it does not require publishing more OCI images.
3. Follow `CONTENT-BOOTSTRAP-SHEET.md` to publish the bundled sample through an approved internal Git destination, pin the actual published commit and generate the matching source, release and standalone request manifests. A local sample, branch name or old lab commit is not a workplace publication.
4. Run only the content adapter for Skill/KnowledgeBase verification. Do not deploy the native HostedAgent adapter. Set the namespace, helper image and exact `SOURCE_CONTROLLER_ORIGIN`, remove lab control-plane scheduling and use its scoped permissions. Apply the generated pinned source and both releases, then wait for actual current-generation Ready conditions and immutable owned ConfigMaps. Preserve file-hash, provenance and ownership checks.
5. Configure the resolved Qwen route as a fixed OpenAI-compatible chat-completions endpoint and model ID. A resolved ModelConfig does not prove Pod connectivity, credential validity or function-call support. Verify the exact endpoint path, DNS, CA trust and network route. Secret and CA ConfigMap references mounted by the Job must exist in its own namespace. Use the existing secret-management process rather than mounting a cross-namespace reference or printing values.
6. Capture the current requests, sources, content ConfigMaps and installed CRDs into a private snapshot. Prepare the explicit standalone HostedAgent and GoldenScenario profile and the Job using `standalone/README.md`. Keep private target values and snapshot data out of this public bundle.
7. Review/apply the guarded schema additions and prepared requests as documented, render from fresh live snapshots, then server-dry-run the emitted Job and ConfigMaps. Apply only the bounded POC objects through the authorized work process.
8. Wait for the Job's Complete condition, check the Pod's terminated exit code and read its sanitized receipt. The content-adapter Deployment remains Running; only the one-shot execution Pod completes. Success requires real model tool calls that load both verified packages, read the required documents and release proofs, and return the required citation/proofs. A Pod merely starting, a Ready CRD, a static render or a model connectivity ping is insufficient.

The Job has no Kubernetes token, arbitrary shell tool or operational Azure/Kubernetes capability. Its only model tools read the pinned skill/knowledge content. Backend errors must remain errors. Do not substitute fixture responses to get a Completed Pod.

## Report the right result

Return the chosen namespace, reused image digest, four CRD establishment checks, content readiness, Job name/Complete condition, container exit code, sanitized model/tool receipt and exact remaining failure if any. Keep private endpoint and source data in private evidence.

Describe a passing run as **a custom-CRD-driven standalone documentation POC without Substrate**. HostedAgent and GoldenScenario are consumed by the offline execution adapter for this one-shot run. This does not prove native kagent Agent/Harness execution or an automatic continuous HostedAgent reconciler.

After this passes, demonstrate a new owner-authored agent definition and content through the same path. Native Harness execution can remain a separate later track.

Native alpha8 schema sources: https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha8/go/api/v1alpha3/harness_types.go and https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha8/go/api/v1alpha3/runtime_types.go

Recorded implementation test: [isolated Kubernetes result](standalone/evidence/kubernetes-test.json). A real Job completed without kagent/Substrate using a deterministic test backend. Real Qwen connectivity and the workplace result remain to be observed.
