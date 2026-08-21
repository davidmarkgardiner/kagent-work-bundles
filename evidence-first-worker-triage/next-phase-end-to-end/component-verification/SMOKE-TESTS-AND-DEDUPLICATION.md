# Controlled Smoke Tests and Deduplication Plan

Run component gates first. These are controlled, non-production tests that
prove the complete Kubernetes channel and its duplicate behaviour; they are
not a licence to collect every log from every namespace.

## What the duplicate controls do

| Layer | Key / purpose | Expected result |
|---|---|---|
| Vector | Delivery key / short in-memory exact-repeat suppression | Stops immediate identical transport repeats before Kafka; not durable across restart. |
| Workflow claim | Stable incident fingerprint / durable approved TTL claim | One active incident produces one GitLab work item; later related evidence updates it. |
| GitLab retry path | Fingerprint label/search | A retry after a partial failure reuses or updates the existing work item rather than blindly creating another. |

Kafka consumer groups manage offsets and work sharing only. They do **not**
deduplicate records, correlate logs with events, or prevent duplicate tickets.

For a work-cluster promotion, use the approved durable TTL claim service. The
old ConfigMap 24-hour proof claim is not a fleet-grade substitute.

## Smoke test rules

- Use one approved non-production namespace and the existing
  `smoke-test.sh` fixtures, or equivalent owner-approved fixtures.
- Give each test a unique harmless marker, for example `E2E-{{RUN_ID}}`.
- Record topic offset/portal timestamp, workflow name, agent response and
  GitLab item ID for every case.
- Wait for the first workflow/ticket to settle before repeating a signal.
- Clean up fixtures after each case. Do not reset production offsets.

## Case A — application log, full-path proof

Emit one allow-listed application error log containing the run marker and a
synthetic secret-shaped value, for example:

```text
ERROR E2E-{{RUN_ID}} unable to reach demo dependency token=not-a-real-token
```

Expected proof chain:

1. Alloy observes the namespace-scoped pod log and forwards it to Vector.
2. Vector classifies it as `log`, redacts the synthetic token, produces Kafka.
3. The EventSource group consumes it and Sensor creates one workflow.
4. The workflow passes the bounded event to the read-only agent.
5. The agent uses AKS MCP read tools against the fixture pod and returns a
   diagnosis.
6. GitLab receives one work item containing the safe event context and
   diagnosis, without the synthetic token.

## Case B — Kubernetes Warning event, full-path proof

Use the existing unschedulable or invalid-image fixture to generate an approved
Warning event such as `FailedScheduling`, `ErrImagePull`, `ImagePullBackOff`,
`BackOff`, or `Failed`. Choose one that is supported by the target cluster and
the Vector/Argo allow-list.

Expected proof chain is the same as Case A, except the envelope has
`signal_kind=event` and carries the Kubernetes reason. The agent must use AKS
MCP to retrieve the matching pod/event evidence read-only.

## Case C — additional safe signals Alloy should collect

Do not widen collection to "all errors." Prove only the approved signal policy:

| Signal | Why test it | Expected route |
|---|---|---|
| Allow-listed app error log | Application failure evidence | Alloy pod logs -> Vector `log` -> Kafka |
| Kubernetes Warning event | Scheduler, image, probe or workload-state evidence | Alloy events -> Vector `event` -> Kafka |
| Representative platform/app log signature | Confirms each newly onboarded namespace emits a usable allow-listed marker | Same log lane, one namespace at a time |
| Rejected routine/non-allow-listed record | Proves safety and efficiency | Vector discard metric increments; no Kafka record/workflow/ticket |

For every namespace, document its agreed error signatures and Warning reasons
before enabling it. If a useful class is rejected, treat it as a versioned
policy change: update the allow-list, repeat Cases A/B, and record the result.

## Case D — exact-repeat suppression

1. Run Case A once and wait for the issue/ticket to be created.
2. Send the identical fixture again within the claim TTL.
3. Verify Vector may suppress an immediate duplicate; if the second record
   reaches Argo, the durable claim must prevent a second ticket.
4. Confirm there is still one active GitLab item and, where policy allows, a
   correlated evidence update rather than a duplicate.

Pass: one incident, one ticket. Fail: two independent GitLab items or an
unexplained missing update.

## Case E — related log then event correlation

1. Run Case A for one fixture workload.
2. Before the TTL expires, cause an allowed Kubernetes Warning event for that
   same workload.
3. Verify the claim/fingerprint resolves both signals to the same incident.
4. Verify the existing GitLab item gains the bounded event context instead of
   a second item.

Pass: one ticket with both sources and a clear timeline. If pod churn changes
the fingerprint, record it as a promotion blocker; do not silently accept two
tickets as correct behaviour.

## Case F — changed incident is not suppressed

Send a second fixture with a different approved reason/signature or a separate
workload. It must create a distinct incident and work item. This prevents an
over-broad fingerprint from hiding real failures.

## Case G — retry/recovery

With owner approval, induce only a controlled backend failure (for example a
temporary test GitLab endpoint denial), then restore it. Verify the workflow's
retry/reconciliation path finds the existing fingerprint-labelled item or
creates exactly one item after recovery. Do not simulate a Confluent outage in
a shared environment without its owner's maintenance approval.

## Evidence and decision table

| Test | Kafka accepted/consumed | Workflow created | AKS MCP read proof | One correct GitLab item | Redaction proof | Result |
|---|---|---|---|---|---|---|
| A log | | | | | | |
| B Kubernetes event | | | | | | |
| C rejected record | n/a | none expected | n/a | none expected | n/a | |
| D exact repeat | | | | one only | | |
| E log + event | | | | one correlated item | | |
| F changed incident | | | | new item expected | | |
| G recovery | | | | one only | | |

Any unexpected ticket, unredacted field, EventSource authorisation error, or
write-capable AKS MCP invocation is a red result and blocks namespace rollout.
