# Work agent: finish the CRD POC without Substrate

Resume from the installed four CRDs and completed image builds. The operator explicitly requires a no-Substrate deployment today. Follow [NO-SUBSTRATE-TODAY.md](NO-SUBSTRATE-TODAY.md) and [standalone/README.md](standalone/README.md).

Do not create Harness, WorkerPool or snapshots. Do not install or upgrade Substrate/kagent, remove required fields from native schemas, switch to a presumed legacy ordinary-Agent API, or wait for platform setup. Use the explicit standalone custom-CRD execution profile supplied here.

## Preserve the work already completed

Keep established CRDs, built images, private configuration, credentials and prior receipts. Check the compatible Python helper image by digest and reuse it. Build/import only genuinely missing or incompatible inputs. Existing OCI content images and native runtime images can stay for later work; this path reads the verified content ConfigMaps and does not need more OCI publication.

The report mentions kagent alpha8 and a Substrate chart version, while the operator says no usable Substrate exists. Record actual served APIs/workloads if needed, but this inconsistency must not turn into a Substrate installation task.

## Bootstrap missing content first

David will provide his personal GitLab repository and push/pull access for this testing POC. **David will ensure the sample files are committed and pushed there before the content bootstrap starts.** The work agent does not own that initial publication prerequisite and must not wait for a separate provider or create another repository, CI pipeline or registry publication.

Once David supplies the repository/ref and access, pull it into a fresh private checkout, verify the two payload paths, resolve and pin the actual full commit SHA, and execute [CONTENT-BOOTSTRAP-SHEET.md](CONTENT-BOOTSTRAP-SHEET.md). David may provide a SHA, but the agent can determine it from the selected ref. Configure working Flux read access to that personal GitLab repo, generate source/releases with `standalone/bootstrap_content.py`, run the content-only adapter and require genuine current-generation readiness and immutable owned ConfigMaps before snapshots and Job preparation. If the URL/access/files are still missing, report that exact prerequisite to David while preserving existing builds. Do not fabricate Ready fields, UIDs or source artifact metadata.

## Execute the bounded Job path

1. Choose any permitted namespace. Keep the four custom requests and verified source/ConfigMap references namespace-local. A native namespace-local Harness, WorkerPool or ModelConfig is not required for this standalone execution.
2. Inspect the existing resolved Qwen ModelConfig without printing Secret values. Identify its real OpenAI-compatible chat-completions URL, model ID, auth mechanism and CA requirements. Configure the Job with that fixed route. Verify DNS, endpoint path, TLS, tool-calling support and allowed network access from the selected namespace.
3. Put required Secret and CA ConfigMap references in the Job's namespace through the existing approved process. Cross-namespace volume/Secret references do not work. Do not mount a kubeconfig or service-account token into the model worker.
4. Follow the standalone guide to render the content-only adapter, compatible additive CRD enum patches, private standalone requests and the one-shot Job. Preserve existing native profiles and installed schemas. Do not deploy the native HostedAgent adapter for this profile.
5. Verify current source revision, immutable release/ConfigMap ownership and file hashes. Use fresh live snapshots for Job preparation. The Job must consume the selected HostedAgent and GoldenScenario and load both complete content packages through its bounded read tools.
6. Review the bounded manifests, server-dry-run them, deploy through the authorized workplace process, and wait for the Job Complete condition and Pod exit code 0. Read the sanitized model/tool receipt. On an actual backend error, report the error and fix that concrete cause; do not substitute fixtures, weaken proof checks or rebuild unrelated images.
7. Return the exact namespace, reused image digest, custom CRD/content checks, Job name/status, exit code, passing receipt or current concrete failure, plus cleanup instructions.

A successful result is a **custom-CRD-driven standalone documentation POC without Substrate**. It is not native kagent Agent/Harness execution or continuous native HostedAgent reconciliation. The current proof is explicit about this scope. Bring an owner-authored agent definition and new content through the same path only after this first Job passes.
