# Restore Istio revision selection after a Kyverno mutation

Incident issue: https://github.com/davidmarkgardiner/kagent-work-bundles/issues/3

Use `rollback-one-deployment.sh` after the GitOps owner stops the bad Kyverno mutation. This handles **namespace or Pod-template `istio.io/rev` label mutation only**, with an existing healthy previous control plane and injector. It does not downgrade an in-place control-plane upgrade, repair gateways, restore mesh configuration, or reverse direct proxy-image mutation. The reported 1.23 to 1.29 versions remain unconfirmed. The fixtures use synthetic revision strings `1-23` and `1-29`; use your exact installed revision or tag, such as `asm-1-23` if applicable.

## Run the patch

Requires Bash, kubectl and jq. The default mode plans the change and performs a server-side namespace dry-run. Only `--apply` writes.

1. Disable or revert the exact offending policy through its GitOps owner. Confirm the live policy and stop BOTH admission and mutate-existing rules. `validationFailureAction: Audit` and `background: false` do not generally disable admission mutation. For a removed policy, check GitOps pruning actually removed the live object. Review pending background work. Preserve existing unrelated security policies.
2. Set the GitOps desired namespace and Pod-template labels to the previous revision so reconciliation does not restore the bad labels. Verify the old istiod, Service endpoints, injector webhook, revision tag mapping and gateway health. A revision label is a selector, not proof the old control plane still exists. Do not uninstall either control plane during recovery.
3. Choose one affected Deployment, its namespace and the exact expected proxy image including registry and tag or digest. Get the image from trusted known-good configuration or a verified healthy Pod. Review the Deployment rollout strategy and available capacity. A namespace label change affects future Pods from every workload in that namespace, although the script rolls only the named Deployment.
4. Run the plan, then the patch using the SAME arguments:

```bash
bash rollback-one-deployment.sh \
  'WORK_CONTEXT' 'APP_NAMESPACE' 'CANARY_DEPLOYMENT' \
  'EXACT_BAD_REV' 'EXACT_GOOD_REV' 'EXACT_EXPECTED_PROXY_IMAGE'

bash rollback-one-deployment.sh \
  'WORK_CONTEXT' 'APP_NAMESPACE' 'CANARY_DEPLOYMENT' \
  'EXACT_BAD_REV' 'EXACT_GOOD_REV' 'EXACT_EXPECTED_PROXY_IMAGE' --apply
```

The script saves private before/after JSON and patches. It checks the observed namespace and Deployment versions with JSON Patch resourceVersion tests. After restoring the namespace label, it submits a dry-run Pod built from the application template. The returned Pod must contain the exact expected proxy image before the Deployment changes. It also dry-runs the Deployment patch. It stops on an unexpected revision, legacy injection label, ambient mode, unsupported Deployment, manual sidecar, injection opt-out, active mutator, image mismatch or API error. It does not retry automatically.

The dry-run Pod is never persisted. Admission dry-runs do not prove connectivity or prevent an asynchronous controller changing labels later. If the script stops after restoring the namespace, that change remains in place. Inspect the printed evidence directory and incident state before any retry. There is no automatic undo into the bad state.

5. Inspect actual replacement Pods, including native sidecars in `initContainers`. Check exact proxy images and readiness, then use `istioctl proxy-status` with the matching Istio CLI and explicit work context. Check the application through its real traffic path, including errors, latency, TLS and dependencies. Rollout readiness alone does not establish recovery. Repeat the controlled rollout only after canary acceptance. StatefulSets, DaemonSets, Jobs and gateways need separate reviewed procedures.

The script never edits existing Pod labels as a proxy downgrade and never patches a running `istio-proxy` image. Istio injection happens when new Pods are created. Keep all saved workplace JSON PRIVATE; it may include application configuration, identifiers and environment values. Do not commit the generated evidence directory.

## Reproduce the mutation offline

Do not apply the fixture policies to any cluster. This reproduction uses the real Kyverno CLI without cluster access:

```bash
bash reproduce-offline.sh
python3 tests/check-script.py
```

The bad policy changes the synthetic Namespace from `1-23` to `1-29`. The restored policy changes that result back to `1-23`. This demonstrates admission mutation, not application breakage, webhook ordering, background mutation, live reinjection or workplace root cause. Deleting the bad policy alone is not a reverse mutation of persisted labels.

`evidence/` contains only synthetic outputs with trailing whitespace normalized, captured with Kyverno CLI 1.14.4 on 2026-11-04. Five API-simulation cases check the shell's write boundaries. No production context has been accessed or changed. No live Istio recovery has been performed.

## Sources

- https://istio.io/latest/docs/setup/upgrade/canary/
- https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/
- https://kyverno.io/docs/policy-types/cluster-policy/mutate/

These were checked on 2026-11-04. Use installed-version documentation and observed webhook configuration when adapting the bundle.
