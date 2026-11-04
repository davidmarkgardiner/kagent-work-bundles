# Recover PeerAuthentication revision selection

Incident issue: https://github.com/davidmarkgardiner/kagent-work-bundles/issues/3

Follow the complete operational sequence in [INCIDENT-RECOVERY-PROCESS.md](INCIDENT-RECOVERY-PROCESS.md), including verification and the conditional canary restart.

## Confirm the revision before any patch

**The latest request mentioned changing back to `1-23`. That conflicts with the earlier report that `1-23` caused the incident and installed Istio is 1.29. The target revision is awaiting operator confirmation.** The numeric examples later in this bundle describe the earlier `1-23 -> 1-29` recovery, not confirmation that either direction is now approved to execute.

Check the actual configured istiod revision and the intended policy scope. Set the observed wrong value and confirmed target explicitly. Do not infer a policy revision from the image version alone.

## Follow this recovery order

1. Confirm the revision and the named affected PeerAuthentications.
2. Stop or correct the offending Kyverno admission and mutate-existing mutation. Confirm the live change.
3. If emergency manual repair requires a Flux pause, suspend only the owning reconcilers using the commands below.
4. Preview and patch each named PeerAuthentication. Preserve its mTLS mode, selector and port overrides.
5. Verify the stored label, effective proxy configuration, actual application traffic and authenticated mTLS.
6. If evidence requires a restart, restart one affected Deployment as a canary, then verify before controlled batches.
7. Correct GitOps desired state before resuming the reconcilers you paused.

**A Flux pause does not stop a live Kyverno mutation. A policy-label patch does not require an automatic cluster-wide restart or node reboot.**

## Pause the specific Flux owner if emergency repair requires it

If the desired fix can reconcile through GitOps, use that path without a pause. If a manual patch needs protection from reconciliation, identify its actual owner first. Record each owner's current `spec.suspend` value and preserve any pre-existing suspension.

Changing validation to Audit or setting `background: false` does not generally stop admission mutation.

Do not suspend the owner before it delivers a needed Kyverno correction. Confirm the bad live mutation has stopped first, or use the incident's separately reviewed containment procedure.

For the owning Kustomization:

```bash
flux --context 'WORK_CONTEXT' suspend kustomization \
  'OWNER_KUSTOMIZATION' -n 'FLUX_NAMESPACE'

kubectl --context 'WORK_CONTEXT' -n 'FLUX_NAMESPACE' \
  get kustomizations.kustomize.toolkit.fluxcd.io 'OWNER_KUSTOMIZATION' \
  -o jsonpath='{.spec.suspend}{"\n"}'
```

The readback must show `true`. A suspension does not cancel a reconciliation already running. Confirm that any in-progress write has finished before a manual patch.

If a HelmRelease directly manages the affected policy, suspend that release as well:

```bash
flux --context 'WORK_CONTEXT' suspend helmrelease \
  'OWNER_HELMRELEASE' -n 'RELEASE_NAMESPACE'

kubectl --context 'WORK_CONTEXT' -n 'RELEASE_NAMESPACE' \
  get helmreleases.helm.toolkit.fluxcd.io 'OWNER_HELMRELEASE' \
  -o jsonpath='{.spec.suspend}{"\n"}'
```

A parent Kustomization may restore a child's suspension setting. Account for the owning parent chain and suspend the relevant parent first when needed. Record that broader scope. A Kustomization pause alone does not stop an independent HelmRelease controller or Kyverno controller.

## Preview and apply the confirmed policy label

Replace every placeholder. These commands contain no assumed target revision:

```bash
bash patch-peerauthentication-revision.sh \
  'WORK_CONTEXT' 'POLICY_NAMESPACE' 'POLICY_NAME' \
  'OBSERVED_WRONG_REV' 'CONFIRMED_TARGET_REV'

bash patch-peerauthentication-revision.sh \
  'WORK_CONTEXT' 'POLICY_NAMESPACE' 'POLICY_NAME' \
  'OBSERVED_WRONG_REV' 'CONFIRMED_TARGET_REV' --apply
```

If the actual target remains `1-29`, substitute bad revision `1-23` and target `1-29`. If the operator intentionally chooses `1-23`, first establish that it is the correct configured policy revision for the affected control plane. Do not reverse the arguments merely to suppress an error.

The script only patches one named PeerAuthentication. It does not disable Flux, disable Kyverno, create a Job, restart workloads or reboot nodes.

## Direct command with hardcoded revisions: 1-23 to 1-29

**Run this only if the confirmed recovery target is `1-29`.** A later request mentioned reversing to `1-23`; that direction remains unconfirmed. Do not run this example if `1-23` is the intended target.

First stop the offending live Kyverno mutation and, if manual repair requires it, pause the specific Flux owners using the procedure above. Save the current policy as private incident evidence. Replace `WORK_CONTEXT`, `POLICY_NAMESPACE` and `POLICY_NAME` with the actual values.

The command tests that the current metadata revision label is `1-23`, then replaces only that label with `1-29`:

```bash
kubectl --context 'WORK_CONTEXT' -n 'POLICY_NAMESPACE' \
  patch peerauthentications.security.istio.io 'POLICY_NAME' \
  --type=json \
  -p='[
    {"op":"test","path":"/metadata/labels/istio.io~1rev","value":"1-23"},
    {"op":"replace","path":"/metadata/labels/istio.io~1rev","value":"1-29"}
  ]'
```

Read the stored label back:

```bash
kubectl --context 'WORK_CONTEXT' -n 'POLICY_NAMESPACE' \
  get peerauthentications.security.istio.io 'POLICY_NAME' \
  -o jsonpath='{.metadata.labels.istio\.io/rev}{"\n"}'
```

Expected output is `1-29`. If the JSON Patch test fails, inspect the current object before another action. Do not remove the test or reverse the values merely to make the command succeed.

This direct command does not save evidence, dry-run admission, check resourceVersion, or compare the spec after the write. Use the bundled script above when those additional checks are required. In both cases, verify the effective mTLS policy and application traffic before considering a targeted restart. Do not reboot nodes or restart every Deployment for this label correction.

## Resume Flux after desired state is corrected

Confirm the GitOps source and any live HelmRelease values contain the intended policy label and corrected mutation rule. Resume only the objects you suspended for this incident. Coordinate parent resumption because it may resume children too.

```bash
# Only if this incident suspended the release.
flux --context 'WORK_CONTEXT' resume helmrelease \
  'OWNER_HELMRELEASE' -n 'RELEASE_NAMESPACE'

# Only if this incident suspended the Kustomization.
flux --context 'WORK_CONTEXT' resume kustomization \
  'OWNER_KUSTOMIZATION' -n 'FLUX_NAMESPACE'
```

Check reconciliation health, then repeat the policy-label and application mTLS checks. Confirm the correction persists through the relevant reconciliation cycle. If the label changes unexpectedly or traffic worsens, stop further changes and inspect the private evidence.

For conditional canary restart commands, follow [step 6 of the incident process](INCIDENT-RECOVERY-PROCESS.md#6-restart-one-deployment-only-if-evidence-requires-it). Do not reboot nodes or restart every Deployment as part of this label-only correction.

## Earlier confirmed incident direction and evidence

**Corrected operator report:** the installed Istio is 1.29. A `PeerAuthentication` was incorrectly labelled `istio.io/rev: "1-23"`. The intended correction is **1-23 -> 1-29 on that policy's metadata label**. This supersedes the initial namespace/proxy downgrade hypothesis. The old `rollback-one-deployment.sh` now refuses execution. Do not run the earlier commit's namespace rollback for this incident.

The label key is assumed to be `metadata.labels["istio.io/rev"]`; confirm that from the actual object. A different field, such as `spec.selector.matchLabels`, requires a different patch. Verify the actual istiod revision is literally `1-29`, rather than deriving it from the binary version. Policy metadata labels are filtered against the configured control-plane revision; a sidecar injection tag is not automatically interchangeable with that revision here.

## Script checks and private evidence

Requires Bash, kubectl and jq. Run from the work operator's authenticated environment.

The script saves private before/after evidence and a JSON Patch. It tests the object's UID, resourceVersion and existing bad label before replacing that label. It performs a server-side dry-run first and refuses a changed spec or incorrect label. After the write, it reads the object back and verifies the desired label and unchanged spec. An already-correct label causes no write. Conflicts and mismatches stop without retry or automatic undo.

The patch preserves `spec.mtls`, `spec.portLevelMtls` and `spec.selector`. It changes no namespaces, workloads, sidecar images or control planes. It does not restart Pods or reinstall Istio. A write may have occurred before a failed post-write check; inspect the saved evidence and active reconcilers before another action. A successful readback is a point-in-time storage check, not proof a background controller cannot change it later.

Keep generated evidence PRIVATE. It contains workplace resource names and configuration. Publish only sanitized summaries.

## Verify mTLS and application recovery

Check policy propagation and the effective configuration on representative affected proxies using the matching 1.29 `istioctl`, the explicit work context and the intended revision. Inspect `istioctl proxy-status`, and inbound listeners and outbound clusters with `istioctl proxy-config`. An ACK or a stored label alone does not prove encryption.

Use the approved application test through the affected client/server path. Check new connections, application errors and TLS failures. Verify authenticated mTLS for the actual traffic, for example trusted Istio traffic telemetry with `connection_security_policy="mutual_tls"`. If the effective policy is STRICT, verify plaintext rejection using an existing approved test. Review more-specific PeerAuthentications and DestinationRules if behavior still differs. `PeerAuthentication` governs inbound acceptance; outbound TLS and policy precedence also matter. Do not change STRICT to PERMISSIVE or DISABLE as part of this label correction.

The reported encryption impact remains unverified here. A revision mismatch can exclude the intended policy, but does not by itself prove all traffic became plaintext. No work cluster was accessed or changed. Do not restart applications as an automatic first step for this configuration-only correction.

## Reproduce the reported mutation offline

Never apply these fixture policies to production.

```bash
bash reproduce-offline.sh
python3 tests/check-script.py
```

The real Kyverno CLI mutates a synthetic PeerAuthentication from `1-29` to the erroneous `1-23`, then the corrected policy restores `1-29`. This proves the label mutation mechanism only. It does not reproduce TLS failure, background reconciliation, live policy propagation or workplace recovery.

`evidence/` records Kyverno CLI 1.14.4 output and eight simulated API checks from 2026-11-04. Trailing whitespace in captured outputs is normalized. The checked cases cover plan-only, successful patch with unchanged spec, already-correct no-op, unexpected label, active mutation, spec mutation, post-write reversion and resource-version conflict.

## Source evidence

Istio 1.29.0's CRD client filters config through `LabelsInRevision`. That function includes unlabelled config and includes all config when the control plane revision is empty; otherwise it requires exact equality with `istio.io/rev`.

- https://github.com/istio/istio/blob/1.29.0/pilot/pkg/config/kube/crdclient/client.go#L454
- https://github.com/istio/istio/blob/1.29.0/pkg/config/model.go#L111-L123
- https://istio.io/v1.29/docs/reference/config/security/peer_authentication/
- https://istio.io/latest/docs/tasks/security/authentication/authn-policy/
- https://kyverno.io/docs/policy-types/cluster-policy/mutate/
- https://fluxcd.io/flux/cmd/flux_suspend_kustomization/
- https://fluxcd.io/flux/cmd/flux_suspend_helmrelease/
- https://fluxcd.io/flux/cmd/flux_resume_kustomization/
- https://fluxcd.io/flux/cmd/flux_resume_helmrelease/

Source behavior was checked on 2026-11-04. The actual installed patch version, vendor customization, configured revision and effective workload policy still require workplace evidence.
