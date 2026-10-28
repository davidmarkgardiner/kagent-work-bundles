# Use David's GitLab content, then run the no-Substrate POC

**Prerequisite owned by David:** David will provide his personal GitLab repository for this testing POC, with push and pull access for the work agent. David will make sure the sample files are already committed and pushed to GitLab before the agent starts the content bootstrap.

**Agent starting point:** pull the provided repository, verify the files and pin the actual commit. Do not make initial content publication, creation of another repository, a CI pipeline or container-registry publication part of this task. Keep the installed CRDs and compatible helper image.

## 1. Confirm David's prerequisite and pull the content

David will supply the HTTPS GitLab clone URL, access and any branch/ref he wants tested. If he supplies a commit, use it. Otherwise, clone the provided branch or repository default branch into a fresh private checkout and record its full 40-character commit SHA. David does not need to calculate that SHA manually.

The committed repository root must contain the unchanged bundled sample:

```text
skills/aks-known-issues/     # five selected files, including licence/provenance
knowledge/aks-bootstrap/    # one cited Markdown document
```

For David preparing those files, export them from the bundle root with:

```bash
python3 -B package.py content --output '{{NEW_CONTENT_SEED_DIRECTORY}}'
```

Commit and push **the contents** of that exported directory to the personal GitLab repository, preserving the bytes, licence, provenance and paths. This is David's prerequisite, not an instruction for the work agent to republish the initial sample.

The work agent then creates a new private bootstrap directory and uses its fresh checkout for the commands below:

```bash
export BOOTSTRAP_DIR='{{NEW_PRIVATE_BOOTSTRAP_DIRECTORY}}'
mkdir -m 700 "$BOOTSTRAP_DIR"
```

Verify the selected commit really exists in the provided GitLab repository and contains both payload paths. A bundled lab commit, image digest or moving branch name is not the content pin. If the repo URL/access or committed files have not yet been supplied, report exactly what David needs to provide; preserve all existing builds and cluster work.

The agent's Git push/pull access and Flux's read access are separate connections. Reuse a working namespace-local Git authentication Secret when needed, or configure the provided repository access through the existing Secret process. Do not put credential values into manifests, logs or Git URLs. The Flux source-controller must be able to reach this personal GitLab repository from the cluster. No internal-only repository requirement is imposed by this POC.

## 2. Generate source, releases and matching standalone requests

With the existing `standalone/private.example.json` already populated privately:

```bash
python3 -B standalone/bootstrap_content.py \
  --config "$PRIVATE_DIR/config.json" \
  --checkout '{{PUBLISHED_CONTENT_GIT_CHECKOUT}}' \
  --git-url '{{DAVID_PERSONAL_GITLAB_HTTPS_CLONE_URL}}' \
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

The adapter uses the configured helper image and exact `SOURCE_CONTROLLER_ORIGIN`. Its source-controller, API and GitLab read access must work. The Job requires no Harness/WorkerPool; this adapter's native API read permission is only for content-deletion checks. Do not deploy the native HostedAgent adapter.

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
