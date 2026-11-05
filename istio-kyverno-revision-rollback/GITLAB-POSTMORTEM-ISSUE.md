# Postmortem: PeerAuthentication activation disrupted application traffic across dev, pre-production and production

**Status:** Draft for incident review. This records a responder's account and proposed improvements; attach the internal evidence before treating the findings as final.

**Incident:** {{INCIDENT_ID}}  
**Change request:** {{CHANGE_REQUEST_ID}}  
**Related merge requests:** {{MERGE_REQUEST_REFERENCES}}  
**Incident review owner:** {{INCIDENT_REVIEW_OWNER}}  
**Severity:** {{CONFIRMED_SEVERITY}}  
**Reported window:** Approximately 19:00 on 4 November to 00:00 on 5 November 2026, Europe/London. Dates and times require confirmation.

## Summary

A Kyverno mutation changed the revision label on Istio PeerAuthentication resources from the previously ineffective value to a value selected by the active control plane. The responder reports this as a change from `1-23` to `1-29`. The policy had existed with the wrong label and had not been enforcing the intended behaviour. Correcting the label therefore activated a security control rather than merely tidying metadata.

Some application traffic paths were not ready for the resulting peer-authentication requirements. Traffic failed after the change became effective. Dev, pre-production and production were affected. This exposed both an application mTLS-readiness gap and a release process that did not prevent an unsafe security-policy activation from reaching production.

The change reportedly passed the usual pull request, peer review and change-request approvals. Those approvals did not prevent the impact. The review must establish what evidence was available, what reviewers were expected to verify, and why the controls did not require successful lower-environment tests and a rehearsed rollback.

Responders neutralised the Kyverno mutation while retaining its object, then used an additional recovery policy or configuration change to allow the owning Flux Kustomization to restore the PeerAuthentication label from GitOps to the previous `1-23` value. Applications reportedly began recovering after reconciliation, approximately 10–20 minutes after that recovery step. The overall incident lasted approximately five hours, with around 40 people involved in the incident call late into the night.

Recovery after reversing the policy activation strongly supports this causal account. The exact policy mode, affected traffic paths, controller actions and complete restoration time still need to be established from evidence.

## Impact

| Area | Reported impact / information still required |
| --- | --- |
| Environments | Application traffic disruption in dev, pre-production and production. Confirm the affected clusters and their individual impact windows privately. |
| Services | Multiple applications affected. Attach an inventory of failed client-to-server paths and business services; do not assume every application or cluster was affected equally. |
| Customers and operations | Production service availability was affected. Confirm failed transactions, delayed work, operational consequences and service-level impact with application owners. |
| Response | Approximately 40 people participated in the incident call. Attendance varied; do not infer total responder-hours from this number. |
| Duration | Approximately five hours from reported onset to restoration. Treat this as an incident-specific estimate, not a measured organisational MTTR. |
| Confidence | The responder reports damage to confidence in the platform and release process. Recovery of trust requires demonstrated corrective controls and published follow-through. |
| Data and security | Data loss, integrity effects, security exposure and any reporting obligations have not been established. Obtain the appropriate internal assessment rather than assuming either harm or absence of harm. |

## Timeline to validate

All times below are approximate and based on the responder account. Replace them with timestamped evidence and distinguish each environment's timeline.

| Time, Europe/London | Reported event | Evidence required |
| --- | --- | --- |
| Before the incident | PeerAuthentication resources existed with a revision label that did not select the intended active control plane. Some traffic paths were not ready for enforcement. | Previous manifests, installed revision configuration, proxy configuration and traffic evidence. |
| Before or around 19:00, 4 Nov | The reviewed Kyverno change relabelled policies to the active revision. Establish when it reached each environment. | Merge and approval records, change record, Flux applied revisions and Kyverno/controller events. |
| Around 19:00 | Application disruption reportedly began. | First failing requests, synthetic checks, service metrics, alerts and incident declaration. |
| Around 23:00 | The reporting responder joined the incident call. Investigation and recovery work were already in progress. | Incident log and decision record. |
| During recovery, exact time unknown | The offending mutation was changed to a dummy/no-op form while its resource remained present. | Exact before/after policy YAML, merge and reconcile timestamps, policy status and evidence that mutation stopped. |
| During recovery, exact time unknown | An additional recovery policy or configuration change allowed the owning Flux Kustomization to restore the label recorded in GitOps. | Exact resource kind and diff, mechanism, source revision and controller evidence. |
| Approximately 10–20 minutes later | Restored labels became effective and applications reportedly began returning online. | Applied policy labels, effective proxy configuration and application traffic recovery. |
| Around 00:00, 5 Nov | Restoration was reported. Confirm whether this was first improvement, complete recovery or incident closure. | Application-owner acceptance and the incident record. |

**Time ambiguity:** The account says “12 pm” but also describes the early hours and a five-hour incident beginning at 19:00. This draft interprets that as midnight, 00:00 on 5 November, rather than noon. Confirm before finalising. Do not classify the full five-hour window as controller reconciliation time; the reported reconciliation portion was 10–20 minutes.

## Technical causal account

**Revision notation:** Treat `1-23` and `1-29` as resource-label strings until checked against the manifests. Do not assume the rollback changed Istio binaries. If the intended software versions are Istio 1.23 and 1.29, these are different minor releases within major version 1, not different major versions. The review should assess release pace against tested compatibility and operational capacity.

### Trigger

The reported trigger was revision-label mutation of existing PeerAuthentication configuration so that the active Istio control plane began consuming it. The change was operationally a policy-enforcement activation, even if its manifest diff appeared to be only a label change.

Istio 1.29.0's configuration client uses revision-label filtering. For a nonempty configured revision, a labelled configuration object must match that revision to be included. Unlabelled objects and an empty control-plane revision have different inclusion behaviour. Verify the actual deployed implementation and settings rather than inferring them from an image tag. [Istio revision filter](https://github.com/istio/istio/blob/1.29.0/pkg/config/model.go#L111-L123), [CRD client](https://github.com/istio/istio/blob/1.29.0/pilot/pkg/config/kube/crdclient/client.go#L454).

### Failure mechanism to confirm

The working explanation is that activating the intended inbound peer-authentication requirements blocked traffic paths that did not meet them. Confirm the actual effective mode, including whether it was `STRICT`, and any mesh-wide, namespace, workload or port-level overrides. Preserve the failed TLS handshakes and the configuration at both ends of representative paths.

PeerAuthentication governs inbound acceptance. Client-side TLS behaviour depends on the mesh path, automatic mTLS, explicit DestinationRules and related configuration. An application can send HTTP to its local proxy while the proxies secure network traffic with mTLS. Plaintext at the application-to-local-proxy hop alone does not prove the network path was unencrypted or the application is inherently incompatible with PeerAuthentication. [Istio TLS configuration](https://istio.io/latest/docs/ops/configuration/traffic-management/tls-configuration/).

The intended security control may have been behaving correctly once selected, while previously tolerated traffic was noncompliant. Validate missing or bypassed proxies, explicit TLS overrides, gateway/backend paths, external clients, certificates and effective policy precedence before assigning a specific technical cause to each failed application. [Istio authentication policy examples](https://istio.io/latest/docs/tasks/security/authentication/authn-policy/).

### Systemic contributors to investigate

- A desired security policy could remain present but ineffective without the gap being detected through runtime assurance.
- The release process did not produce an effective stop before the change affected production. Establish whether dev testing was absent, unrepresentative, failed, or not enforced as a promotion gate.
- A shared mutation may have exposed multiple environments to the same change without a proven environment boundary. Confirm the actual promotion order and scope; cross-environment impact alone does not establish simultaneous deployment.
- The change and approval process did not demonstrate adequate assessment of enforcement activation, application compatibility, scope and recovery.
- A verified rollback for the actual Flux and Kyverno ownership model was not available to the responders. Confirm whether a rollback existed and, if so, why it did not restore service promptly.

The approval records must be reviewed for their effectiveness. Multiple approvals are not evidence that the technical effect was understood or tested. Equally, the incident account alone does not establish that individual reviewers acted carelessly. Determine what the process required and what information, expertise and challenge it supplied.

## What restored availability

The responder describes this sequence:

1. The team updated the Kyverno mutation into a dummy/no-op form, retaining the policy object but preventing the original mutation.
2. Removing the policy from GitOps alone was not considered sufficient to delete the live resource because pruning was not enabled or available for that managed resource in this setup.
3. The team introduced another recovery policy or configuration change that allowed Flux reconciliation to restore the GitOps PeerAuthentication label to `1-23`.
4. Reconciliation and the observed label reset took approximately 10–20 minutes. Application traffic then began recovering.

Capture the exact YAML and ordering. The additional recovery resource's kind and mechanism are not established by this account. Do not replace this history with the direct `kubectl` loop discussed during the incident: those were proposed commands, not evidence that they were executed. No workload restart or node reboot is established by the recovery account either.

Verify that the “dummy” policy was genuinely inert and valid, rather than causing admission errors or failing webhook requests. Confirm both admission and mutate-existing processing stopped; retaining an object or changing one background setting alone is not sufficient proof. [Kyverno mutation behaviour](https://kyverno.io/docs/policy-types/cluster-policy/mutate/).

Flux supports garbage collection through `.spec.prune`; per-resource exclusions and ownership also matter. “Removing the manifest did not delete the object in our configuration” is different from “Flux cannot delete policies.” Record the actual Kustomization settings, resource inventory, exclusions and ownership. Do not enable pruning across a shared Kustomization as an unreviewed emergency fix. [Flux pruning](https://fluxcd.io/flux/components/kustomize/kustomizations/#prune).

**Restored availability is not restored security assurance.** Returning the policy to a revision that the active control plane ignores may deliberately recreate the previous enforcement gap. Record the effective post-mitigation state, obtain explicit time-bounded risk ownership, and plan safe re-enablement after application readiness is proven. Do not silently describe the previous baseline as secure.

## Why restoration took too long

The responder's assessment is that approximately five hours to reverse this change was too slow. The review should account for the elapsed time without assuming where all of it was spent.

Break the timeline into detection, escalation, causal diagnosis, mitigation decision, change preparation/approval, controller reconciliation, proxy propagation and application validation. Identify the longest avoidable delays and set an agreed recovery target for comparable changes.

Investigate whether responders knew the live Kyverno rule, its background behaviour, the Flux owner and the no-prune lifecycle. Establish whether a safe emergency reconciliation path was available and whether the team understood when a manual reconcile would help. Flux supports explicitly requesting reconciliation; that is a mechanism to validate and rehearse, not evidence that every 10–20 minute delay can be eliminated. [Flux reconcile command](https://fluxcd.io/flux/cmd/flux_reconcile_kustomization/).

## Evidence to attach privately

- [ ] Exact PeerAuthentication resources before activation, during impact and after mitigation, including labels, complete specs and scopes.
- [ ] Installed Istio images, configured revisions, revision tags and representative proxy connections/configuration. Confirm the literal `1-23` and `1-29` values. The spoken forms “1.2.3”, “1.2.9” and “123” must not be treated as verified binary versions.
- [ ] Original Kyverno mutation, dummy/no-op replacement and additional recovery resource, including admission/background settings and controller status.
- [ ] Flux source and applied revisions, Kustomization inventory, pruning settings, resource exclusions, events and reconciliation timestamps for each environment.
- [ ] Release, review, approval and change-request records, including the test and rollback evidence supplied to approvers.
- [ ] Affected application and dependency inventory, first failures, TLS errors, traffic/security telemetry and recovery checks using new connections.
- [ ] Environment promotion chronology and the controls that allowed or blocked progression.
- [ ] Incident decisions, participation, escalation timing and communications, with customer and business-impact assessment.

Keep internal links, identities, service names, raw logs and sensitive configuration in the internal issue or restricted evidence store. This public Markdown intentionally uses placeholders.

## Corrective actions proposed for agreement

Priorities and deadlines below are proposals, not existing assignments or approved commitments. Assign a named accountable owner and a calendar due date to each accepted action in GitLab. Avoid closing actions solely on documentation or approval-count changes.

| ID | Priority / proposed timing | Proposed accountable role | Action and completion evidence |
| --- | --- | --- | --- |
| A1 | P0, before policy re-enablement | Platform incident owner + security owner | Confirm post-mitigation effective security state in every affected environment. Record the residual enforcement gap, risk owner, expiry, monitoring and conditions for re-enablement. |
| A2 | P0, before the next related change | Release engineering owner | Enforce dev -> pre-production -> production promotion with recorded application/mTLS acceptance and a separate production gate. Prove that failure in an earlier environment prevents promotion of the same immutable change artifact. |
| A3 | P0, before re-enablement | Application owners + mesh owner | Build a client-to-server readiness matrix covering mesh, legacy, gateway and external paths. Capture successful authenticated mTLS and expected rejection of noncompliant traffic where required. Fix or explicitly risk-accept every exception. |
| A4 | P0, before the next related release | Platform engineering owner | Rehearse rollout and rollback under the same Kyverno, Flux ownership and pruning settings. Demonstrate mutation containment, persisted rollback and application recovery within an agreed timed target. Include a mutation that overwrites manual repairs. |
| A5 | P1, within one week | Change process owner | Review the actual approvals. Require an explicit statement of behavioural effect, scope, lower-environment results, stop conditions and tested rollback. Require relevant technical challenge and application-owner evidence for enforcement changes. Audit a subsequent change against these criteria. |
| A6 | P1, within one week | Platform policy owner | Inventory dormant or mislabelled security policies and compare intended enforcement with effective runtime behaviour. Create alerts/checks for policy presence without intended enforcement, with owner and exception handling. |
| A7 | P1, within one week | GitOps owner | Define the lifecycle of non-pruned policies, retirement of the no-op rule and the additional recovery resource. Test that each resource can be made inert, retired or restored predictably without unrelated deletion. Record scope, owner and expiry for emergency artifacts. |
| A8 | P1, before the next enforcement rollout | SRE + mesh owner | Use a bounded canary population with representative traffic, error/TLS/SLO thresholds and explicit hold points. Prove an injected compatibility failure stops wider rollout. Prevent a shared policy change bypassing environment boundaries. |
| A9 | P1, within two weeks | Incident management owner | Reconstruct stage timings, identify avoidable delay and agree a restoration objective. Run a timed exercise with a named incident commander, technical lead, scribe and application validators; retain the results. |
| A10 | P1, within two weeks | Observability owner | Provide tested alerts and dashboards for failed requests, TLS handshake failures, effective mTLS traffic and policy changes. Exercise detection using the same class of fault and record alert latency. |
| A11 | P2, within two weeks | Platform release owner | Review release cadence, supported-version policy and reviewer/on-call capacity against actual test coverage and recovery capability. Do not infer unsafe cadence from revision-label numbers alone. Demonstrate a release with the agreed controls. |
| A12 | P1, review within one week | Engineering leadership / review owner | Publish the agreed findings and action owners internally. Report action progress and the next successful staged release/rollback exercise to stakeholders to rebuild confidence. |

Use staged canary evaluation and objective promotion criteria rather than relying on a change being small or having several approvals. [Google SRE canary guidance](https://sre.google/workbook/canarying-releases/). Review the process without personal blame while retaining accountable owners and verifiable actions. [Google SRE postmortem guidance](https://sre.google/sre-book/postmortem-culture/).

## Questions the review must answer

1. What exact policy behaviour became active, and which client-to-server paths failed because of it?
2. How long had the policy been ineffective, and why did security assurance not detect that state?
3. In what order did the change reach dev, pre-production and production? What evidence allowed each promotion?
4. What risk, scope, compatibility and rollback evidence was in the review/change record, and what was missing?
5. What exactly did the no-op mutation and recovery resource do? Why did this work under the actual ownership/pruning configuration?
6. How much time was spent at each recovery stage, and which tested mechanism would shorten the next incident?
7. Which intended controls remain inactive after mitigation, who owns that risk, and when will compliant enforcement be restored?

## Review acceptance

- [ ] Application, platform, security, release/change and incident-management representatives have reviewed this account.
- [ ] The incident date, midnight/noon ambiguity, per-environment impact and restoration timestamps are resolved.
- [ ] Root cause and contributors are supported by the attached evidence; unsupported claims are removed or labelled.
- [ ] The technical recovery sequence and post-mitigation security position are confirmed.
- [ ] Every agreed action has a named owner, due date and measurable acceptance evidence in GitLab.
- [ ] Any required customer, operational or compliance follow-up is assessed through the organisation's process.
- [ ] A follow-up review and safe re-enablement plan are scheduled.

Availability mitigation alone does not close the remediation work. Close the postmortem when the review is agreed and action tracking is established; track the outstanding fixes and security risk to their own evidence-based completion.
