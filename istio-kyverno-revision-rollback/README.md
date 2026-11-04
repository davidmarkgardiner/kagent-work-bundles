# Recover PeerAuthentication revision selection

Incident issue: https://github.com/davidmarkgardiner/kagent-work-bundles/issues/3

Follow the complete operational sequence in [INCIDENT-RECOVERY-PROCESS.md](INCIDENT-RECOVERY-PROCESS.md), including verification and the conditional canary restart.

## Confirm the revision before any patch

**The operator has explicitly confirmed the requested direction as `1-29 -> 1-23`. All active patch examples below now use that direction.** This replaces the earlier `1-23 -> 1-29` instructions.

Verify that `1-23` is the correct configured control-plane revision for the affected policies. Istio was previously reported as installed version 1.29. A version number and configured revision are different values. If istiod is configured only as `1-29`, changing the policy label to `1-23` may exclude the policy from that control plane. This patch does not install or downgrade Istio, and no healthy `1-23` control plane has been verified here.

## Inspect PeerAuthentication labels before patching

Show every PeerAuthentication and its metadata labels in the current cluster:

```bash
kubectl get peerauthentications.security.istio.io -A --show-labels
```

Describe every policy across all namespaces. Inspect the `Labels:` section for `istio.io/rev`:

```bash
kubectl describe peerauthentications.security.istio.io -A
```

To inspect one policy in detail:

```bash
kubectl -n 'POLICY_NAMESPACE' \
  describe peerauthentications.security.istio.io 'POLICY_NAME'
```

To list only policies currently labelled `1-29`, which match the current rollback loop:

```bash
kubectl get peerauthentications.security.istio.io -A \
  -l 'istio.io/rev=1-29' --show-labels
```

These commands are read-only. The metadata label `istio.io/rev` is different from workload labels under `spec.selector.matchLabels`. Inspect the metadata label before choosing a patch. Keep detailed workplace output private.

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

The current requested arguments are observed revision `1-29` and target revision `1-23`. Do not reverse them merely to suppress an error.

The script only patches one named PeerAuthentication. It does not disable Flux, disable Kyverno, create a Job, restart workloads or reboot nodes.

## Direct command with hardcoded revisions: 1-29 to 1-23

**The operator-requested recovery target is now `1-23`.** Confirm that revision is correct for the affected policies before applying.

First stop the offending live Kyverno mutation and, if manual repair requires it, pause the specific Flux owners using the procedure above. Save the current policy as private incident evidence. Replace `WORK_CONTEXT`, `POLICY_NAMESPACE` and `POLICY_NAME` with the actual values.

The command tests that the current metadata revision label is `1-29`, then replaces only that label with `1-23`:

```bash
kubectl --context 'WORK_CONTEXT' -n 'POLICY_NAMESPACE' \
  patch peerauthentications.security.istio.io 'POLICY_NAME' \
  --type=json \
  -p='[
    {"op":"test","path":"/metadata/labels/istio.io~1rev","value":"1-29"},
    {"op":"replace","path":"/metadata/labels/istio.io~1rev","value":"1-23"}
  ]'
```

Read the stored label back:

```bash
kubectl --context 'WORK_CONTEXT' -n 'POLICY_NAMESPACE' \
  get peerauthentications.security.istio.io 'POLICY_NAME' \
  -o jsonpath='{.metadata.labels.istio\.io/rev}{"\n"}'
```

Expected output is `1-23`. If the JSON Patch test fails, inspect the current object before another action. Do not remove the test or reverse the values merely to make the command succeed.

This direct command does not save evidence, dry-run admission, check resourceVersion, or compare the spec after the write. Use the bundled script above when those additional checks are required. In both cases, verify the effective mTLS policy and application traffic before considering a targeted restart. Do not reboot nodes or restart every Deployment for this label correction.

## Loop over matching policies across all namespaces: 1-29 to 1-23

**Use this only after confirming that every matched policy should target `1-23`.** If some policies intentionally belong to `1-29`, use individual named-policy patches instead. A mesh-root policy may affect the whole mesh.

First stop the offending Kyverno admission and mutate-existing mutation. Pause the relevant Flux owners if manual repair requires it, and account for their parent reconcilers. The loop does not perform those containment steps.

From the bundle directory, replace `WORK_CONTEXT` and preview all policies that currently carry the incorrect metadata label:

```bash
CTX='WORK_CONTEXT'

kubectl --context "$CTX" get peerauthentications.security.istio.io \
  -A -l 'istio.io/rev=1-29'
```

Review every namespace and policy name. The apply command queries the matching set again, so include any changes since the preview in the incident review. Run in the same Bash session:

```bash
(
  set -euo pipefail
  : "${CTX:?Set CTX to the work context first}"

  kubectl --context "$CTX" get peerauthentications.security.istio.io \
    -A -l 'istio.io/rev=1-29' -o json |
  jq -r '.items[] | [.metadata.namespace, .metadata.name] | @tsv' |
  while IFS=$'\t' read -r ns name; do
    echo "Patching PeerAuthentication $ns/$name: 1-29 -> 1-23"

    bash ./patch-peerauthentication-revision.sh \
      "$CTX" "$ns" "$name" '1-29' '1-23' --apply
  done
)
```

Requires the local `patch-peerauthentication-revision.sh`, Bash, kubectl and jq. Each script invocation saves private evidence, dry-runs admission, checks object identity and resourceVersion, and verifies the desired label and unchanged policy spec.

The loop stops on the first failure. Earlier successful patches remain applied. There is no batch rollback or automatic retry. Keep each printed evidence directory in the private incident record. A failed post-write check means the current policy may also have been changed.

Read back any remaining `1-29` labels:

```bash
kubectl --context "$CTX" get peerauthentications.security.istio.io \
  -A -l 'istio.io/rev=1-29'
```

No matching objects is only a label inventory result. Verify effective policy, authenticated mTLS and application traffic for the affected paths, then confirm the correction survives reconciliation. The loop does not restart Deployments, reboot nodes or resume Flux.

## Patch matching policies using the current kube context

Use this kubectl-only command for the confirmed **1-29 -> 1-23** correction in the cluster you are already logged into. It needs no Flux CLI, jq or local patch script. Stop the offending Kyverno mutation first and pause the relevant Flux owners if required. Confirm every matched policy should target `1-23`, including mesh-root policies.

```bash
(
  set -euo pipefail
  kubectl get peerauthentications.security.istio.io -A \
    -l 'istio.io/rev=1-29' \
    -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\n"}{end}' |
  while read -r ns name; do
    kubectl -n "$ns" patch peerauthentications.security.istio.io "$name" \
      --type=json -p='[
        {"op":"test","path":"/metadata/labels/istio.io~1rev","value":"1-29"},
        {"op":"replace","path":"/metadata/labels/istio.io~1rev","value":"1-23"}
      ]'
  done
)
```

This changes only matching policies' metadata revision labels. It stops on the first API or patch failure, with earlier writes left applied. It does not perform the bundled script's evidence capture, admission dry-run or post-write spec checks. An active mutator can overwrite the repair. Verify stored labels, effective mTLS and application traffic afterward. Do not automatically restart workloads or reboot nodes.

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

## Superseded directions

The current operator-requested policy correction is **1-29 -> 1-23**. Earlier messages and earlier Git commits used the opposite direction. Do not use those old commands for this request. The old namespace rollback entrypoint remains disabled; this change concerns PeerAuthentication metadata labels only.

Confirm the actual label key is `metadata.labels["istio.io/rev"]`. A change inside `spec.selector.matchLabels` needs a different patch. Preserve existing mTLS mode, port overrides and workload selector.

## Script checks and private evidence

Requires Bash, kubectl and jq. Run from the work operator's authenticated environment.

The script saves private before/after evidence and a JSON Patch. It tests the object's UID, resourceVersion and existing bad label before replacing that label. It performs a server-side dry-run first and refuses a changed spec or incorrect label. After the write, it reads the object back and verifies the desired label and unchanged spec. An already-correct label causes no write. Conflicts and mismatches stop without retry or automatic undo.

The patch preserves `spec.mtls`, `spec.portLevelMtls` and `spec.selector`. It changes no namespaces, workloads, sidecar images or control planes. It does not restart Pods or reinstall Istio. A write may have occurred before a failed post-write check; inspect the saved evidence and active reconcilers before another action. A successful readback is a point-in-time storage check, not proof a background controller cannot change it later.

Keep generated evidence PRIVATE. It contains workplace resource names and configuration. Publish only sanitized summaries.

## Verify mTLS and application recovery

Check policy propagation and the effective configuration on representative affected proxies using the matching 1.29 `istioctl`, the explicit work context and the intended revision. Inspect `istioctl proxy-status`, and inbound listeners and outbound clusters with `istioctl proxy-config`. An ACK or a stored label alone does not prove encryption.

Use the approved application test through the affected client/server path. Check new connections, application errors and TLS failures. Verify authenticated mTLS for the actual traffic, for example trusted Istio traffic telemetry with `connection_security_policy="mutual_tls"`. If the effective policy is STRICT, verify plaintext rejection using an existing approved test. Review more-specific PeerAuthentications and DestinationRules if behavior still differs. `PeerAuthentication` governs inbound acceptance; outbound TLS and policy precedence also matter. Do not change STRICT to PERMISSIVE or DISABLE as part of this label correction.

The reported encryption impact remains unverified here. A revision mismatch can exclude the intended policy, but does not by itself prove all traffic became plaintext. No work cluster was accessed or changed. Do not restart applications as an automatic first step for this configuration-only correction.

## Historical offline evidence from the earlier direction

These retained fixtures and evidence demonstrate the earlier, opposite correction `1-23 -> 1-29`. They have not been rerun or relabelled as proof for the newly requested target `1-23`. The patch script accepts explicit bad and good revision arguments. Never apply these fixture policies to production.

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
