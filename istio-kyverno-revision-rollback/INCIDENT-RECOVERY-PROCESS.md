# Recover after an incorrect PeerAuthentication revision label

**Revision confirmation is pending.** A later request mentioned reversing to `1-23`, which conflicts with the earlier recovery target below. Confirm the intended revision before running numeric patch commands. See [the README confirmation and Flux pause/resume procedure](README.md#confirm-the-revision-before-any-patch). This runbook's `1-23 -> 1-29` examples apply only if `1-29` is confirmed.

Use this process for the reported `PeerAuthentication` label correction **1-23 -> 1-29**, after stopping the offending Kyverno mutation through GitOps.

The installed Istio is reported as 1.29. Confirm the actual configured control-plane revision is exactly `1-29`. This process corrects `metadata.labels["istio.io/rev"]` on identified policies. It does not downgrade Istio or change namespace injection labels.

**Do not restart every Deployment across the cluster as an automatic recovery step.** First patch the policy, verify propagation and test application traffic. Use the conditional restart procedure below only when evidence supports it.

Incident: https://github.com/davidmarkgardiner/kagent-work-bundles/issues/3

Script: [patch-peerauthentication-revision.sh](patch-peerauthentication-revision.sh)

## 1. Identify the affected policies and preserve evidence

Run these commands from the work operator's authenticated environment. Replace all placeholder values. Keep the resulting evidence private.

```bash
WORK_CONTEXT='{{WORK_CONTEXT}}'
POLICY_NAMESPACE='{{POLICY_NAMESPACE}}'
POLICY_NAME='{{POLICY_NAME}}'
CONTROL_PLANE_NAMESPACE='{{CONTROL_PLANE_NAMESPACE}}'
WORKLOAD_NAMESPACE='{{WORKLOAD_NAMESPACE}}'
AFFECTED_POD='{{AFFECTED_POD}}'

umask 077
INCIDENT_EVIDENCE=$(mktemp -d "${TMPDIR:-/tmp}/peer-auth-incident.XXXXXXXX")

kubectl --context "$WORK_CONTEXT" -n "$POLICY_NAMESPACE" \
  get peerauthentications.security.istio.io "$POLICY_NAME" -o yaml \
  > "$INCIDENT_EVIDENCE/policy-before.yaml"

kubectl --context "$WORK_CONTEXT" -n "$CONTROL_PLANE_NAMESPACE" \
  get deployments -l app=istiod -o json \
  > "$INCIDENT_EVIDENCE/istiod-before.json"
```

Inspect the saved policy and confirm the bad value is the metadata revision label. Preserve its complete spec, including mTLS mode, port overrides and workload selector. If the wrong field is inside `spec.selector`, stop and prepare a different patch.

Inspect the installed istiod image, configured revision and affected proxies' control-plane connection. An image version of 1.29 alone does not prove the revision string is `1-29`. If your installation uses different istiod labels, use its actual Deployment name to collect that evidence.

Identify every affected policy explicitly. A policy without a selector in the mesh root namespace can affect the whole mesh. A namespace-scoped policy can affect multiple Deployments. Do not infer the affected set from the policy name alone.

## 2. Stop the incorrect mutation through GitOps

1. Identify the exact Kyverno rule and its GitOps owner.
2. Disable or correct that rule through the existing delivery process. Preserve unrelated security rules.
3. Confirm reconciliation completed and the live rule is corrected or absent. If removing a policy, confirm pruning actually removed it.
4. Include admission mutation and mutate-existing background processing. Review outstanding background work that could restore the bad label.
5. Set the affected PeerAuthentication's desired GitOps metadata revision label to `1-29`.

Changing validation to Audit or setting `background: false` does not generally disable admission mutation. Do not proceed while an active reconciler keeps restoring `1-23`.

If GitOps already corrected the stored policy, the script reports an already-correct label and performs no write. Continue with verification.

If emergency repair requires a Flux pause, follow [the targeted pause and resume commands](README.md#pause-the-specific-flux-owner-if-emergency-repair-requires-it). Confirm the bad live Kyverno mutation is stopped first. Preserve pre-existing suspension states, account for parent reconcilers, and confirm in-progress reconciliation has finished.

## 3. Preview and apply one policy correction

Run the preview from the bundle directory. Requires Bash, kubectl and jq.

```bash
bash patch-peerauthentication-revision.sh \
  "$WORK_CONTEXT" "$POLICY_NAMESPACE" "$POLICY_NAME" '1-23' '1-29'
```

Inspect the printed plan and private evidence directory. The dry-run must preserve the complete policy spec and return the desired revision label.

Apply the correction with the same inputs:

```bash
bash patch-peerauthentication-revision.sh \
  "$WORK_CONTEXT" "$POLICY_NAMESPACE" "$POLICY_NAME" '1-23' '1-29' --apply
```

The script tests the UID, resourceVersion and current bad label, then replaces only that label. It reads the policy back and checks the desired label and unchanged spec. Record the printed evidence directory in the private incident record.

Repeat only for the explicitly identified affected policies. The script handles one named policy per invocation. It is a shell script, not a Kubernetes Job. If your organisation requires a Job, use the existing approved runner and reviewed identity; do not grant cluster-wide patch or restart access to run this script.

If the script stops, inspect its evidence before another attempt. A post-write failure means a write may already have occurred. There is no automatic retry or undo into `1-23`.

## 4. Verify stored state and effective policy

Read the policy again:

```bash
kubectl --context "$WORK_CONTEXT" -n "$POLICY_NAMESPACE" \
  get peerauthentications.security.istio.io "$POLICY_NAME" -o yaml \
  > "$INCIDENT_EVIDENCE/policy-after.yaml"
```

Confirm the revision remains `1-29` across the relevant GitOps and background reconciliation cycle. Confirm the mTLS mode, port overrides and selector match the before evidence.

Use the matching Istio CLI to inspect control-plane sync and representative affected proxies:

```bash
istioctl --context "$WORK_CONTEXT" --revision '1-29' proxy-status \
  > "$INCIDENT_EVIDENCE/proxy-status-after.txt"

istioctl --context "$WORK_CONTEXT" -n "$WORKLOAD_NAMESPACE" \
  proxy-config listeners "$AFFECTED_POD" -o json \
  > "$INCIDENT_EVIDENCE/listeners-after.json"

istioctl --context "$WORK_CONTEXT" -n "$WORKLOAD_NAMESPACE" \
  proxy-config clusters "$AFFECTED_POD" -o json \
  > "$INCIDENT_EVIDENCE/clusters-after.json"
```

Check effective inbound mTLS and the relevant clients' outbound TLS configuration. Inspect both ends of the affected path when they run in different Pods. A stored label or synced status alone does not prove encryption or application recovery.

## 5. Test application traffic before any restart

Use an existing approved application probe through the affected client-to-server path. Test new connections so old connection pools do not hide current behavior.

Confirm successful application responses, acceptable errors and latency, and authenticated mTLS on the actual traffic. For example, inspect trusted Istio traffic telemetry with `connection_security_policy="mutual_tls"`. If the effective policy is STRICT, verify plaintext rejection through an approved test.

PeerAuthentication controls inbound acceptance. More-specific policies, port overrides and outbound DestinationRules can change the result. If traffic still fails, inspect those effective settings and TLS errors before widening the change.

Do not weaken STRICT to PERMISSIVE or DISABLE as part of this label correction. Do not report that encryption is restored solely because the label is fixed.

## 6. Restart one Deployment only if evidence requires it

A PeerAuthentication configuration correction normally propagates to existing proxies. If policy and application verification pass, skip restarts.

If evidence identifies stale application connections or a workload-specific condition that requires a restart, document that reason in the incident. Confirm the intended policy has propagated first. Review the Deployment's strategy, available replicas, readiness checks, capacity and traffic impact. A Deployment rollout uses its configured strategy; do not assume a PodDisruptionBudget makes a broad rollout safe.

Set one affected Deployment name and run a canary restart:

```bash
DEPLOYMENT_NAME='{{AFFECTED_CANARY_DEPLOYMENT}}'

kubectl --context "$WORK_CONTEXT" -n "$WORKLOAD_NAMESPACE" \
  rollout restart "deployment/$DEPLOYMENT_NAME"

kubectl --context "$WORK_CONTEXT" -n "$WORKLOAD_NAMESPACE" \
  rollout status "deployment/$DEPLOYMENT_NAME" --timeout=180s
```

Repeat the application and mTLS checks on the replacement Pods. If readiness, error rates or TLS behavior worsen, stop further restarts and preserve the evidence. Do not automatically retry or revert the policy to the known incorrect revision.

Only after canary acceptance, proceed through the incident's named affected Deployments in controlled batches. Verify each batch before continuing. Do not use a cluster-wide restart command or include unrelated system workloads. StatefulSets, DaemonSets, Jobs and gateways require their own reviewed procedures.

## 7. Record acceptance and close the incident

Complete this checklist with fresh workplace evidence:

- [ ] The exact offending Kyverno mutation is stopped or corrected in desired and live state.
- [ ] All identified PeerAuthentications have the intended revision in desired and stored state.
- [ ] Their complete specs remain unchanged.
- [ ] The affected proxies have the intended effective policy.
- [ ] Approved application tests pass on new connections.
- [ ] Authenticated mTLS is verified on the affected traffic paths.
- [ ] Any required canary and subsequent restarts passed verification, or restarts were unnecessary.
- [ ] Corrected GitOps desired state is delivered and incident-paused Flux owners are resumed, preserving pre-existing suspensions.
- [ ] The correction persists through reconciliation and the agreed observation period.
- [ ] Private evidence and timestamps are attached to the internal incident record.

No workplace cluster was accessed or changed when this runbook was prepared. The bundle's offline mutation reproduction and simulated API checks do not establish production recovery.

## References

- [Bundle evidence and reproduction](README.md)
- https://github.com/istio/istio/blob/1.29.0/pilot/pkg/config/kube/crdclient/client.go#L454
- https://github.com/istio/istio/blob/1.29.0/pkg/config/model.go#L111-L123
- https://istio.io/latest/docs/tasks/security/authentication/authn-policy/
- https://kyverno.io/docs/policy-types/cluster-policy/mutate/
