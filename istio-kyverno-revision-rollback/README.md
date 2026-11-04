# Correct a PeerAuthentication revision label to 1-29

Incident issue: https://github.com/davidmarkgardiner/kagent-work-bundles/issues/3

**Corrected operator report:** the installed Istio is 1.29. A `PeerAuthentication` was incorrectly labelled `istio.io/rev: "1-23"`. The intended correction is **1-23 -> 1-29 on that policy's metadata label**. This supersedes the initial namespace/proxy downgrade hypothesis. The old `rollback-one-deployment.sh` now refuses execution. Do not run the earlier commit's namespace rollback for this incident.

The label key is assumed to be `metadata.labels["istio.io/rev"]`; confirm that from the actual object. A different field, such as `spec.selector.matchLabels`, requires a different patch. Verify the actual istiod revision is literally `1-29`, rather than deriving it from the binary version. Policy metadata labels are filtered against the configured control-plane revision; a sidecar injection tag is not automatically interchangeable with that revision here.

## Patch one policy after stopping the bad mutation

Requires Bash, kubectl and jq. Run from the work operator's authenticated environment.

1. Stop or correct the exact Kyverno mutation through its GitOps owner, including mutate-existing/background work. Confirm the live policy changed or was pruned. Audit validation mode and `background: false` do not generally stop admission mutation. Align the PeerAuthentication's GitOps desired label to `1-29` so reconciliation does not reintroduce `1-23`.
2. Inspect the named PeerAuthentication and its current label, complete spec, namespace and scope. Inspect the healthy installed istiod revision and the affected proxies' connection. A policy without a selector in the mesh root namespace can have mesh-wide scope. Keep that existing scope unchanged.
3. Preview the change, replacing every placeholder:

```bash
bash patch-peerauthentication-revision.sh \
  'WORK_CONTEXT' 'POLICY_NAMESPACE' 'POLICY_NAME' '1-23' '1-29'
```

4. Apply the same correction:

```bash
bash patch-peerauthentication-revision.sh \
  'WORK_CONTEXT' 'POLICY_NAMESPACE' 'POLICY_NAME' '1-23' '1-29' --apply
```

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

Source behavior was checked on 2026-11-04. The actual installed patch version, vendor customization, configured revision and effective workload policy still require workplace evidence.
