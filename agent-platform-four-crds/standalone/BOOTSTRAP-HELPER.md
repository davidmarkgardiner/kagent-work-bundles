# Offline content bootstrap helper

David will provide his personal GitLab repository and push/pull access for this testing POC. He will ensure that the unchanged sample files are already committed and pushed before the agent starts. The work agent then pulls the repository, verifies `skills/aks-known-issues/` and `knowledge/aks-bootstrap/` at the committed root, resolves the actual full commit SHA and uses a local checkout containing those Git objects. David may provide a SHA; otherwise the agent determines it from the selected branch/ref. There is no initial Git publication, CI pipeline or container-registry task for the agent. See [CONTENT-BOOTSTRAP-SHEET.md](../CONTENT-BOOTSTRAP-SHEET.md).

```sh
python3 -B standalone/bootstrap_content.py \
  --config PRIVATE_CONFIG_JSON --checkout LOCAL_CONTENT_GIT \
  --git-url APPROVED_HTTPS_GIT_URL --commit FULL_40_HEX_COMMIT \
  --release-id crd-poc-v1 --git-auth-secret LOCAL_GIT_SECRET_NAME \
  --output NEW_PRIVATE_DIR
```

Omit `--git-auth-secret` when unnecessary. It accepts only a Git-auth Secret name in the configured namespace. Git and model authentication have different purposes; select the correct approved references. The helper does not inspect Secret contents or impose a Secret-name policy. The helper reads no credentials. It rejects URL credentials, queries, fragments, non-HTTPS/non-`.git` URLs, unresolved placeholders, unsafe Git entries and content bytes that differ from the bundled manifests. It reads committed Git objects, so dirty worktree files cannot change the output. Git lazy fetching and protocols are disabled. A release ID is a lowercase DNS slug of at most 16 characters.

The new directory is mode `0700` and its three files are mode `0600`. `source-and-releases.json` contains the commit-pinned Flux GitRepository plus Skill and KnowledgeBase releases. `requests.json` contains the standalone HostedAgent and exact-citation GoldenScenario with matching release pins and a regenerated HostedAgent spec hash. `bootstrap-receipt.json` records the names, commit, selected-byte verification and explicit unverified target gates. Existing output is never overwritten.

Use the real Flux source-controller and the compatible content-only adapter described in [README.md](README.md) to materialize the releases as controller-owned immutable ConfigMaps. Review and deliver the generated manifests through the target's approved process, then capture actual Ready source/release objects and immutable ConfigMap data before running `prepare.py`. The helper does not publish Git, approve a source, deploy objects, create Ready metadata, or create content ConfigMaps. Its source ignore selects the two payload directories; other files within those directories can still increase the Flux artifact. Verify actual Flux artifact sizes against the receipt's compressed, expanded and per-release content limits.

Run the offline Git and rendering checks with `python3 -B -m unittest discover -s standalone -p 'test_bootstrap_content.py' -v`. Their synthetic Ready metadata is confined to tests and establishes neither remote publication nor workplace readiness.
