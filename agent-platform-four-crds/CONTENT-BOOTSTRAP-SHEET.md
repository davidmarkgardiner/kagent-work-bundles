# Bootstrap the missing content, then run the no-Substrate POC

The work agent's blocker is valid. Installed CRDs and bundled Markdown do not create verified releases or immutable ConfigMaps. **Bootstrap the content before preparing the Job.** Reuse the installed CRDs and compatible helper image.

The requested payload is the unchanged bundled synthetic AKS documentation sample. The work agent owns its publication/bootstrap work within the existing POC authorization and workplace access. Use an approved internal Git destination and the existing publication process. Prepare the concrete seed and publication diff; do not wait for a new content design or provider-created Kubernetes releases. The public bundle does not itself establish workplace approval, publish to internal Git or make a source Ready. If an explicit workplace publication gate applies, return that named gate and the prepared artifacts.

## 1. Export and publish the provided sample

From the bundle root, choose a new private bootstrap directory:

```bash
export BOOTSTRAP_DIR='{{NEW_PRIVATE_BOOTSTRAP_DIRECTORY}}'
mkdir -m 700 "$BOOTSTRAP_DIR"
python3 -B package.py content --output "$BOOTSTRAP_DIR/content-seed"
```

Publish **the contents** of `content-seed/` into an approved internal Git repository. An existing approved repository can be reused by adding these paths through its normal delivery flow. The helper limits Flux delivery to the two payload directories. The repository root must contain:

```text
skills/aks-known-issues/     # five selected files, including licence/provenance
knowledge/aks-bootstrap/    # one cited Markdown document
```

Preserve the sample bytes, licence, provenance and paths for this first proof. Do not replace an existing repository or overwrite unrelated content. Use its normal authenticated Git workflow. Record the published full 40-character commit and verify remote read-back through the approved Git service. A local commit, bundled lab commit, image digest or branch name is not that publication receipt.

Required private inputs are the approved HTTPS Git URL, published commit, a local checkout containing that exact commit, and an existing namespace-local Git authentication Secret reference when needed. Git and Qwen authentication have different purposes; select the correct existing Git credential reference. Preserve the Git service's established CA/authentication configuration.

If publication cannot proceed, return the exact missing repository destination, publishing permission or credential-reference name and who must supply it. Do not restart image builds or ask for a provider-created Kubernetes release: the next steps create those releases.

## 2. Generate source, releases and matching standalone requests

With the existing `standalone/private.example.json` already populated privately:

```bash
python3 -B standalone/bootstrap_content.py \
  --config "$PRIVATE_DIR/config.json" \
  --checkout '{{PUBLISHED_CONTENT_GIT_CHECKOUT}}' \
  --git-url '{{APPROVED_INTERNAL_HTTPS_GIT_URL}}' \
  --commit '{{ACTUAL_PUBLISHED_40_HEX_COMMIT}}' \
  --release-id crd-poc-v1 \
  --output "$BOOTSTRAP_DIR/manifests"
```

Add `--git-auth-secret '{{NAMESPACE_LOCAL_GIT_AUTH_SECRET}}'` only when needed. This helper verifies the committed Git objects against both bundled file manifests, preserves their content hashes and sets the actual source commit. It emits:

- `source-and-releases.json`: one full-commit-pinned Flux GitRepository, one Skill and one KnowledgeBase.
- `requests.json`: standalone HostedAgent and GoldenScenario with matching release pins and a regenerated HostedAgent spec hash.
- `bootstrap-receipt.json`: exact generated names and local verification results.

It performs no Git push or Kubernetes/model call and does not claim publication or readiness. The source excludes all directories except the two selected payload paths. The actual Flux artifact must still remain within the adapter's 2 MiB compressed and 8 MiB expanded bounds. Do not point it at the entire work-bundles repository.

For `--release-id crd-poc-v1`, the generated names are `content-crd-poc-v1`, `aks-known-issues-crd-poc-v1`, `aks-bootstrap-crd-poc-v1`, `docs-crd-poc-v1` and `docs-proof-crd-poc-v1`. Check the receipt. Use a new release ID if an existing immutable request has different pins.

## 3. Install the content-only adapter and materialize both packages

Set `$TARGET_CONTEXT` explicitly and set `$NS` to `config.json.namespace`. Capture only the installed CRDs and API discovery for adapter preparation:

```bash
export SNAPSHOT_DIR="$BOOTSTRAP_DIR/snapshot"
mkdir -m 700 "$SNAPSHOT_DIR"
kubectl --context "$TARGET_CONTEXT" get crd \
  skills.skills.platform.kagent.dev knowledgebases.skills.platform.kagent.dev \
  hostedagents.skills.platform.kagent.dev goldenscenarios.skills.platform.kagent.dev \
  -o json > "$SNAPSHOT_DIR/crds.json"
kubectl --context "$TARGET_CONTEXT" get --raw /apis/api.kagent.dev/v1alpha3 \
  > "$SNAPSHOT_DIR/native-api-resources.json"
python3 -B standalone/prepare.py \
  --config "$PRIVATE_DIR/config.json" --snapshot "$SNAPSHOT_DIR" \
  --output "$BOOTSTRAP_DIR/adapter" --adapter-only
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$BOOTSTRAP_DIR/adapter/content-adapter.json"
kubectl --context "$TARGET_CONTEXT" apply \
  -f "$BOOTSTRAP_DIR/adapter/content-adapter.json"
kubectl --context "$TARGET_CONTEXT" -n "$NS" rollout status \
  deployment/skill-adapter --timeout=180s
kubectl --context "$TARGET_CONTEXT" apply --dry-run=server \
  -f "$BOOTSTRAP_DIR/manifests/source-and-releases.json"
kubectl --context "$TARGET_CONTEXT" apply \
  -f "$BOOTSTRAP_DIR/manifests/source-and-releases.json"
```

The adapter uses the configured helper image and exact `SOURCE_CONTROLLER_ORIGIN`. Its source-controller, API and internal Git access must work. The Job requires no Harness/WorkerPool; this adapter's native API read permission is only for content-deletion checks. Do not deploy the native HostedAgent adapter.

For the example release ID, wait on the actual generated resources:

```bash
kubectl --context "$TARGET_CONTEXT" -n "$NS" wait --for=condition=Ready \
  gitrepository/content-crd-poc-v1 \
  skill/aks-known-issues-crd-poc-v1 \
  knowledgebase/aks-bootstrap-crd-poc-v1 --timeout=180s
```

Confirm Ready conditions match each object's current generation. Check the source's actual artifact revision/digest and each release's `status.configMapRef.name`, `contentSha256` and `observedSourceRevision`. The referenced ConfigMaps must really exist, be immutable, and have the correct release owner UID and bytes.

If materialization fails, inspect `skill-adapter` logs and release reason codes. Resolve the actual source auth/CA, artifact-origin, RBAC, network, size or file-hash error. Never patch Ready status, fabricate UIDs/artifact metadata, manually substitute unverified ConfigMaps or weaken integrity checks.

## 4. Snapshot and run the bounded Qwen proof

Follow [standalone/README.md](standalone/README.md) to apply only the guarded standalone enum additions, then server-dry-run/apply the generated `manifests/requests.json`. Do not wait for native HostedAgent Ready.

Export fresh `skill.json`, `knowledge.json`, `hosted.json`, `golden.json`, `sources.json`, `configmaps.json` and `crds.json` from the cluster. Both releases reference the **same** GitRepository: export it once and wrap it as a List, not as duplicate entries. Use the live `status.configMapRef.name` values for the two ConfigMaps.

Render the standalone Job from those snapshots, server-dry-run it, apply it, then require Job Complete, Pod exit code 0 and a passing sanitized receipt from the real configured Qwen route. The content-adapter Deployment remains Running.

Report the final result as **a custom CRD-driven standalone documentation POC without Substrate**. Keep Git publication, Flux/content readiness and real model execution as separate observed gates. No native kagent Agent/Harness claim, Substrate installation or platform upgrade is involved.
