# Demonstrate a Kyverno policy regression and verified recovery

For an office handoff, start with [Reproduce the dashboard recovery demonstration
in an office sandbox](OFFICE-HANDOFF.md). It includes configuration, runtime,
budget, role-binding, GitOps and CI examples plus target acceptance checks.

This extension connects the existing application-remediation demonstration to
the [OTel agent-flow dashboard](../otel-agent-flow/README.md). It adds a concrete
Kyverno fault fixture and a recovery view in that same dashboard. The
[connected runtime](live/README.md) adds a durable admission ledger, bounded
real-model classifier, scoped GitLab/Kubernetes MCP tools, and native Kyverno
skills. Its live rehearsal uses a dedicated demo repository and namespace.
The workplace agent must bind these to the existing delivery and approval flow.

The [dashboard-controlled flow](live/DASHBOARD-FLOW.md) adds a **Start demonstration**
button and a durable incident timeline. Human approval happens in the dashboard.
Kagent then merges the exact reviewed commit. A separate native verification
task and measured live recovery must pass before
the controller resolves the GitLab issue. See [validation](VALIDATION.md) for the
actual rehearsal outcomes, including the subsequent fresh completed run.

The specialist runs alongside the application as an application-owned agent
profile. It does not modify the Kyverno controller binary. Kubernetes watches
and selected telemetry feed a narrow admission gate before model classification.
Only the admitted incident reaches the remediation agent.

## The incident the audience sees

The healthy policy permits images from `docker.io/library/*`. A Git change
misspells that pattern as `docker.io/libary/*`. Kyverno consequently rejects
the valid demo application. This is a real admission failure caused by a policy
regression, not a broken Kyverno engine or a fabricated Kubernetes Event.

The specialist reads the current denial, the matching policy/rule, the current
Git revision, and its Kyverno runbook. It identifies the registry typo and
proposes the one-field repository fix. CI checks the policy contract at the
exact proposed head; an independent reviewer checks that head and its results.
Actual positive and negative Kyverno admissions are verified separately. Retain
the existing human merge gate. After merge, the agent waits for GitOps and
independently verifies that the valid fixture passes while an unapproved image
is still denied. Only then can the recovery view turn green.

The local `run-lab-proof.py` script exercises the real policy behavior and a
small HTTP application. It applies the fixture policies directly as operator
setup. It does not call a model, create a GitLab MR, execute GitOps, invoke an
agent, or fabricate OTel. Its receipt explicitly marks those stages NOT RUN.

## Connect the two existing work bundles

Give the implementing work agent this folder, the updated `otel-agent-flow`
folder, and the earlier working remediation implementation. Start from
[the integration instructions](../otel-agent-flow/KYVERNO-RECOVERY.md).
Use the [design](https://github.com/davidmarkgardiner/kagent-work-bundles/blob/main/docs/plans/kyverno-application-specialist.md) for
critical-only admission and durable incident identity.

1. Discover the existing successful remediation entrypoint, ordinary/native
   kagent API, ModelConfig, tool names, GitLab project and policy path, approval
   ledger, GitOps owner, dashboard configuration, and telemetry exporters.
2. Keep one canonical incident ID, run ID, native task binding, and reviewed
   profile revision across those systems. Preserve the existing delivery and
   approval semantics. The read-only OTel receiver receives no GitLab or Kubernetes
   credentials. The separate trusted operator bridge records dashboard approval;
   native tools cannot approve their own remedy.
3. Put the healthy policy and fixture tests in the dedicated demo repository.
   Match only the test namespace and the labelled fixture. Add an actual
   application Deployment through the established delivery path. Its Pod
   template uses the same labels and admitted image as the valid fixture.
4. Establish valid admission, invalid denial, and application HTTP baseline.
   Capture revision, resource identities, and the application generation.
5. Introduce the faulty policy through the dedicated GitLab/GitOps test path.
   Drive a new application rollout or fresh fixture admission, because an
   existing running Pod is not retroactively stopped by this policy change.
   Observe repeated policy-specific rejection. A policy-denied rollout can
   leave the old replica serving; display rollout failure separately from HTTP
   availability instead of claiming an outage that did not occur.
6. Pass the deterministic critical-candidate gate before the bounded real
   classifier. Retain its actual decision and the accepted kagent task receipt.
   A scripted decision can test routing only and must remain labelled fixture.
7. Let the specialist diagnose and propose the typo correction from observed
   evidence. Do not present a prewritten transcript as model investigation.
   Require the two admission tests, independent review, and human decision on
   the exact head before merge.
8. Wait for GitOps source and applied revisions to equal the actual merge SHA.
   Read back the actual policy content and observed generation. If the served
   Policy API omits it, retain null and use the documented stable-read and
   active-admission proof variant. Wait for the
   application rollout and HTTP probes too. Source sync alone does not establish
   recovery. Publish the terminal agent verification receipt after those checks.
9. Publish a bounded, fresh recovery snapshot from the trusted observer. Record
   the underlying receipts privately. Compare the dashboard's projected state
   with those independent reads before calling the demonstration complete.
10. Rehearse duplicate observations, collector restart, missing telemetry, changed
    MR head, classifier exhaustion, failed recovery, and expired health evidence.
    Failures must remain visible and must not create repeated investigations.

## Connected components

- [Runtime and role boundaries](live/README.md): six fixed tools, a transactional
  SQLite ledger, exact-head CI/review/approval gates, and recovery verification.
- [Classifier](live/CLASSIFIER.md): a stateless real model call through the
  durable budget proxy, with twelve classification reservations per run and
  no retry or fallback. Only critical decisions at confidence 0.95 or greater
  can admit the allowlisted condition.
- `live/collect_probe.py`: an operator-only collector that brackets actual
  Kubernetes dry-run probes with stable policy reads and corroborates the
  current blocked rollout. It grants no Pod-create permission to an agent.
- `skills/`: two native skill packages for investigation and reviewed Kyverno
  knowledge. Publish the actual reviewed sources as digest-pinned OCI content.
- `live/viewer.py`: a read-only view of activity received by the existing OTel
  dashboard plus strict recovery receipts. It mounts no model, Kubernetes,
  GitLab, or approval credentials and exposes no action endpoint.

The initial collector deliberately exercises only this synthetic policy fault.
It is not yet a general log/event ingestion service or a production deployment
injection policy. Use [VALIDATION.md](VALIDATION.md) for the current proof boundary.

## Run the bounded local policy proof

Use the explicitly isolated local kind cluster. The script refuses another
context, a different node identity, an existing demo namespace, and an existing
receipt output. It restores the healthy policy in `finally` and retains the
dedicated namespace and application for inspection. Inspect any failed cleanup
before continuing.

Install a pinned Kyverno version compatible with Kubernetes 1.35 before running
the proof. The source session used chart `3.9.2` and Kyverno `v1.19.2`.
Provide a private kubeconfig path and a fresh receipt path:

```sh
python3 run-lab-proof.py \
  --context kind-kyverno-agent-poc \
  --kubeconfig '{{PRIVATE_LAB_KUBECONFIG}}' \
  --output '{{PRIVATE_EVIDENCE_DIRECTORY}}/kyverno-admission.json'
```

Expected checks are three successful valid admissions in the baseline, three
policy-specific rejections under the faulty policy, three successful admissions
after repair, an invalid-image denial in every phase, and three successful HTTP
reads from the application before and after repair. The script also verifies a
real blocked Recreate rollout with a policy-specific FailedCreate event and the
final current Deployment generation. These immediate probes establish policy
behavior. They do not satisfy the longer classification window in the design.

## Extend to Informer after its contract is identified

The repository references an `informer` namespace, but this does not identify
its application source, health endpoint, deployment owner, or desired-state
repository. Clarify whether Informer means that named application or Kubernetes
informer/watch machinery before changing either integration.

If it is the named application, reuse the incident/trace/recovery contract with
an Informer-specific profile, skill, allowed fault, repository path, and positive
and negative health tests. Do not reuse Kyverno policy probes as application
health proof. If it means Kubernetes informer machinery, use watches for
selected objects with resync and reconnect handling, then verify recovered state
with current API reads. A stale informer cache is not an authorization decision
or final recovery proof.
