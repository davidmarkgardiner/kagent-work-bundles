# 24-Hour Deduplication and Noise-Control Contract

Use this before enabling the Alloy -> Vector -> Kafka -> Argo triage path for
real workloads. The intended outcome is one investigation and one ticket for a
stable incident identity in 24 hours—even if a pod is recreated, Vector
restarts, Kafka replays, or matching records arrive concurrently.

## TL;DR

The current repository has useful pieces, but they are **not by themselves a
24-hour no-noise guarantee**:

- Vector's `dedupe` transform has a bounded, process-local event cache. It
  reduces exact repeats but resets on restart and is not a 24-hour store.
- The management workflow's durable 24-hour claim protects agent investigation
  and ticket creation, but its Sensor has already created a workflow first.
- The applied proof configuration derives `dedupe_key` from the literal pod
  name. A replacement pod therefore produces a different key; this is a
  recorded defect, not a production-ready dedupe design.

Do not declare the path fleet-ready until the stable identity, atomic durable
claim, and pre-workflow admission gate below are proven.

## The two keys have different jobs

| Key | Job | Includes | Never includes |
|---|---|---|---|
| `incident_key` | 24-hour business idempotency: one investigation/ticket | cluster, namespace, stable workload identity, normalised signal/reason class | pod name/UID, timestamp, raw message, evidence text, retry count |
| `delivery_key` | Cheap local suppression of equivalent repeats | `incident_key` plus bounded normalised evidence signature | secrets, raw unbounded log, transient timestamp |

Kafka records should use `incident_key` as their message key for stable
partition affinity. Kafka message keying does **not** itself deduplicate.

## Stable workload identity is mandatory

The key must survive normal ReplicaSet/Pod churn. Prefer an identity that logs
and events can derive consistently:

```text
cluster : namespace : workload_kind : workload_name : signal_class : reason_class
```

`workload_name` is the controller name (Deployment, StatefulSet, DaemonSet or
Job), not a ReplicaSet or pod name. For a Deployment, derive it from an
authoritative owner/label mapping—never by blindly stripping a suffix from an
arbitrary pod name.

Kubernetes events often lack the same labels as logs. If the event path cannot
derive the same stable controller identity, enrich it before it joins this
dedupe domain or quarantine it. Do not use `unknown`, which would suppress
unrelated incidents together.

## Correct control-plane shape

```text
Alloy -> Vector -> Kafka triage.candidates [key = incident_key]
                 |
                 v
    durable admission/claim (atomic create-if-absent; TTL = 24h)
       |-- duplicate -> metric/audit only; no Argo workflow
       `-- first claim -> Kafka triage.accepted -> Argo -> one workflow
```

This placement is material. A Sensor cannot ask the claim store before it
creates a Workflow. If the requirement is **no duplicate workflow at all**, the
durable claim must occur before the EventSource/Sensor topic, not only as the
workflow's first step.

Keeping the existing in-workflow claim is still good defence in depth: it must
stop the kagent and GitLab steps. It is not enough for the strict no-load goal.

## Atomic 24-hour claim requirements

The claim store must use `incident_key` as its unique key and atomically return
`claimed` or `duplicate` (compare-and-swap or unique insert; never
delete-then-create). It must:

- expire 24 hours after the first accepted observation;
- retain safe first/last-seen and count metadata without extending the window
  by default;
- recover a claim that was made but did not create/update a ticket; and
- expose metrics for claim, duplicate, error and expiry outcomes.

If a critical escalation is allowed to break the window, make that a deliberate
policy change to `signal_class`/`reason_class`, not an accidental key change
caused by a new pod or altered log line.

## Vector's limited role

Vector should filter early, redact/bound evidence, and use `delivery_key` to
suppress local repeats. It cannot be the only authority because the cache is
bounded and process-local.

The slim worker base has an `incident_fingerprint` built from
`cluster:namespace:workload:reason`, while its `delivery_key` also includes
safe evidence. The applied proof config uses literal `.pod` in `dedupe_key`.
Neither proves the target design until controller identity is verified for both
log and event paths.

## Required payload contract

```json
{
  "schema_version": "observability.triage.v{{VERSION}}",
  "source_pipeline": "alloy-vector-evidence",
  "incident_key": "{{STABLE_SHA256}}",
  "delivery_key": "{{BOUNDED_REPEAT_SHA256}}",
  "workload_kind": "Deployment",
  "workload_name": "{{WORKLOAD}}",
  "signal_class": "pod-crashloop",
  "reason_class": "BackOff",
  "automation_allowed": false
}
```

The management validator rejects blank, `unknown`, or pod-derived
`incident_key` values for workload-scoped signals. Ticket labels and all retry
searches use the same `incident_key` prefix.

## Mandatory proof matrix

| Test | Expected result |
|---|---|
| Same log/event repeated inside 24h | One accepted message/workflow/ticket; later signals are duplicate metrics only |
| Same workload, replacement pod name | Same `incident_key`; no second workflow, investigation or ticket |
| Vector restart then same signal | Durable admission rejects it; restart cannot reset the window |
| Kafka replay / EventSource restart | Durable admission rejects it |
| Concurrent identical candidates | Exactly one atomic claim and one accepted workflow |
| Different workload in same namespace | Different keys; both may be accepted |
| Same workload, policy-approved different reason class | Explicitly recorded new/suppressed decision |
| Claim succeeds but ticket step fails | Retry updates/reuses one fingerprinted ticket; no second ticket |
| 24h plus safety margin elapsed | A new incident can be accepted if the signal persists |

Run the replacement-pod test with a Deployment/ReplicaSet, record both pod
names, and prove the stable `incident_key` did not change.

## Noise and load guardrails

- Begin with allowlisted namespaces, reason classes and severity.
- Keep Sensor rate limits plus workflow deadline, TTL and pod/PVC cleanup.
- Alert on candidate volume, accepted claims, duplicate ratio, claim errors,
  workflow creations and ticket creates.
- Suspend the Alloy EventSource through GitOps when claim errors or accepted
  volume exceed the approved pilot threshold.
- Preserve duplicate counters and redacted metadata for audit, but never call
  kagent or create a GitLab ticket for a duplicate.

## Copy/paste instruction for the work agent

> Prove that 24-hour dedupe uses a stable controller-level incident key, not a
> pod name, UID, timestamp or evidence text. Treat Vector dedupe only as
> best-effort load reduction. Locate the atomic durable claim and prove it runs
> before the Argo intake topic when no duplicate workflow is required. Run the
> replacement-pod, Vector restart, Kafka replay and concurrent-claim tests. Do
> not declare ready while the applied configuration keys the incident from
> literal `.pod`.

## Relevant repository evidence

- [Worker Vector envelope and local dedupe](../../kustomize/base/worker.yaml)
- [Recorded pod-churn defect](../../next-phase-end-to-end/ROLLOUT-TRACKER.md)
- [Deduplication smoke tests](../../next-phase-end-to-end/component-verification/SMOKE-TESTS-AND-DEDUPLICATION.md)
- [Workflow lifecycle and shared Kafka routing](workflow-lifecycle-and-shared-kafka-routing.md)
