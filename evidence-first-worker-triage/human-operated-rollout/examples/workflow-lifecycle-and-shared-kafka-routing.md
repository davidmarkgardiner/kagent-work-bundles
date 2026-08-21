# Workflow Lifecycle and Shared Kafka Routing Contract

Use this when the Alloy/Vector evidence path and Alertmanager currently share
a Kafka topic. It prevents two separate problems:

1. completed or stuck Argo Workflows accumulating indefinitely; and
2. Alertmanager and Alloy records being split, dropped, or cross-triggering
   because independent EventSources share a Kafka consumer group.

This is an adapt-and-prove example. Confirm the installed Argo Events and Argo
Workflows CRD schemas before applying it.

## TL;DR

- A Kafka **consumer group is not a routing rule**. Consumers in the same group
  divide topic partitions/messages between themselves.
- Never put the Alertmanager EventSource and Alloy evidence EventSource in the
  same consumer group. Each independent pipeline needs its own group.
- Add a producer-owned envelope discriminator such as
  `source_pipeline: alloy-vector-evidence`; the Alloy triage Sensor filters on
  it, schema version, `automation_allowed: false`, and signal kind.
- The workflow validates the same contract again, has a deadline and cleanup
  policy, and is activated/deactivated through GitOps—not by leaving an
  unbounded Sensor live by accident.

## Why the current shared-group shape is unsafe

```text
Shared topic
  ├─ Alertmanager record
  └─ Alloy/Vector evidence record

EventSource A: Alloy triage       consumer group = shared-group
EventSource B: Alertmanager       consumer group = shared-group
```

Kafka gives each message to one member of `shared-group`, not to both. If
EventSource A receives an Alertmanager record and its Sensor rejects it, that
record has still been consumed for that group. EventSource B may never see it.
The inverse can lose Alloy evidence. Sensor filters run **after** the Kafka
consumer-group assignment; filters cannot repair a shared-group design.

Sensors themselves consume from the Argo EventBus. The Kafka group is owned by
the EventSource, so it is the EventSource `consumerGroup.groupName` that must
be unique per independently meaningful Kafka consumer.

## Target routing design

### Preferred: separate topics and ACLs

```text
Vector -> observability.alloy-evidence.v3 -> alloy-evidence EventSource
Alertmanager -> observability.alerts.v1   -> alertmanager EventSource
```

Give each EventSource a principal/ACL that can read only its own topic. This is
the cleanest operational and security boundary.

### Transitional: shared topic, separate groups, explicit envelope source

Until topics are split, both consumers receive the full shared-topic stream,
but use different groups and strict filters:

```text
shared topic
  ├─ alloy-evidence EventSource  group {{ENV}}-alloy-evidence-triage-v1
  └─ alertmanager EventSource    group {{ENV}}-alertmanager-triage-v1
```

This does not reduce broker traffic, but it prevents one pipeline from
stealing the other pipeline's messages. Monitor non-matching records and
consumer lag until the topic split is complete.

## Required producer contract

Vector owns this field; do not infer it from a namespace, title, or free-text
log message:

```json
{
  "schema_version": "observability.triage.v{{VERSION}}",
  "source_pipeline": "alloy-vector-evidence",
  "signal_kind": "event",
  "automation_allowed": false,
  "cluster": "{{WORKER_CLUSTER}}",
  "namespace": "{{NAMESPACE}}",
  "incident_fingerprint": "{{FINGERPRINT}}",
  "evidence": {"summary": "{{REDACTED_SUMMARY}}"}
}
```

Alertmanager must use its own incompatible source value and schema, for
example:

```json
{
  "schema_version": "alertmanager.v1",
  "source_pipeline": "alertmanager",
  "status": "firing"
}
```

Do not let either producer set the other producer's discriminator. If Kafka
producers use distinct principals, enforce that separation with topic ACLs as
well as the payload contract.

## EventSource and Sensor example

Use a unique consumer group for the Alloy evidence EventSource:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: EventSource
metadata:
  name: {{ALLOY_EVIDENCE_EVENTSOURCE}}
  namespace: {{ARGO_EVENTS_NAMESPACE}}
spec:
  kafka:
    alloy-evidence:
      url: {{KAFKA_BOOTSTRAP}}
      topic: {{SHARED_OR_ALLOY_TOPIC}}
      consumerGroup:
        groupName: {{ENV}}-alloy-evidence-triage-v1
        oldest: false
      jsonBody: true
      # TLS/SASL secret references omitted: use the approved local values.
```

Filter the Sensor on the producer contract. The event sensor may further split
`log` and `event` into separate dependencies, but both must include the source
filter:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Sensor
metadata:
  name: {{ALLOY_EVIDENCE_SENSOR}}
  namespace: {{ARGO_EVENTS_NAMESPACE}}
spec:
  eventBusName: {{EVENTBUS_NAME}}
  dependencies:
    - name: alloy-evidence
      eventSourceName: {{ALLOY_EVIDENCE_EVENTSOURCE}}
      eventName: alloy-evidence
      filters:
        data:
          - path: body.schema_version
            type: string
            value: ["observability.triage.v{{VERSION}}"]
          - path: body.source_pipeline
            type: string
            value: ["alloy-vector-evidence"]
          - path: body.automation_allowed
            type: bool
            value: ["false"]
          - path: body.signal_kind
            type: string
            value: ["log", "event"]
  triggers:
    # Reference the bounded Workflow template below.
    - template:
        name: {{ALLOY_TRIAGE_TRIGGER}}
        rateLimit:
          requestsPerUnit: {{MAX_TRIAGE_WORKFLOWS}}
          unit: Minute
```

The current slim base manifest filters schema version and
`automation_allowed`; it should gain the `source_pipeline` and `signal_kind`
filters before a shared-topic production rollout. Workflow validation repeats
the same source/schema rule so a direct or malformed trigger cannot bypass it.

## Workflow lifecycle: bounded execution and cleanup

Add these controls to the generated Workflow or its `WorkflowTemplate` spec:

```yaml
spec:
  # Stops a hung agent, GitLab call, or downstream dependency.
  activeDeadlineSeconds: {{TRIAGE_WORKFLOW_DEADLINE_SECONDS}}

  # Remove completed Workflow CRs only after their required evidence/log export.
  ttlStrategy:
    secondsAfterSuccess: {{TRIAGE_SUCCESS_TTL_SECONDS}}
    secondsAfterFailure: {{TRIAGE_FAILURE_TTL_SECONDS}}
    secondsAfterCompletion: {{TRIAGE_COMPLETION_TTL_SECONDS}}

  # Remove pods immediately after their logs/evidence have been exported.
  podGC:
    strategy: OnWorkflowCompletion

  # Do not leave workflow-created PVCs behind.
  volumeClaimGC:
    strategy: OnWorkflowCompletion
```

Choose values through environment configuration. Failure retention should be
long enough for a human to inspect the failed workflow, but never unlimited.
Before enabling TTL/pod GC, prove that the durable evidence is available
elsewhere: redacted ticket, workflow archive or log backend, metrics, and a
correlation/fingerprint record. Do not use a short TTL as a substitute for
observability.

The workflow should also contain:

- a strict payload-validation first step;
- the existing idempotency/deduplication claim before agent or GitLab work;
- a rate limit at the Sensor; and
- a namespace-level ResourceQuota/parallelism boundary sized for the approved
  pilot.

## Activation and emergency stop

Do not use a payload field such as `triage_enabled: false` as the primary stop
switch: the EventSource can still consume and commit messages while the Sensor
filters them out, losing the backlog for that group.

Use a GitOps-controlled activation boundary instead:

| State | GitOps action | Kafka effect |
|---|---|---|
| Prepared, not live | Do not reconcile the Alloy EventSource/Sensor, or suspend the owning Flux Kustomization | No Alloy consumer group advances |
| Live pilot | Reconcile the explicitly named Alloy EventSource and Sensor | Only its dedicated group advances |
| Emergency stop | Suspend/remove the Alloy EventSource first, then Sensor | Stops new Kafka consumption before stopping workflow triggers |
| Planned cleanup | Wait for in-flight workflows, archive required evidence, then remove EventSource/Sensor and confirm group/ACL decision | No orphan workflow resources; offsets preserved or deliberately retired |

If the installed GitOps controller cannot suspend one resource safely, use a
dedicated Kustomization for the Alloy ingestion pair. Do not scale a controller
deployment to zero as the routine control plane, because that can affect other
EventSources.

## Proof tests before enabling

1. Produce one valid Alloy log/event envelope and one Alertmanager envelope to
   the shared topic.
2. Confirm both dedicated consumer groups receive their own copies.
3. Confirm the Alloy Sensor creates a workflow only for the Alloy envelope.
4. Confirm Alertmanager receives no Alloy workflow and Alloy creates no
   workflow for the Alertmanager envelope.
5. Send an invalid/missing `source_pipeline` envelope: it must create no
   workflow and raise a monitored contract-mismatch signal.
6. Force a bounded downstream failure; verify `activeDeadlineSeconds`, failure
   retention, pod GC and durable evidence behave as configured.
7. Exercise the GitOps emergency stop and prove no new offsets advance for the
   Alloy group while stopped.
8. Confirm deduplicated/replayed Alloy messages do not create a second ticket
   or agent investigation.

## Copy/paste instruction for the work agent

> Inspect the actual EventSource `consumerGroup.groupName`, topic, Sensor
> dependency filters, Workflow TTL/pod-GC settings and GitOps ownership. Do
> not apply a shared consumer group to the Alertmanager and Alloy EventSources.
> Add and prove a producer-owned `source_pipeline: alloy-vector-evidence`
> envelope field, then require it at the Alloy Sensor and workflow validator.
> Use separate consumer groups during the shared-topic transition, with
> separate topics/ACLs as the target state. Verify the stop procedure halts the
> EventSource before it stops the Sensor, and prove workflow cleanup preserves
> required durable evidence.
