# Noise control and capacity guide

The triage path uses several independent brakes. No single one is enough.

```text
Alloy scope -> Vector tier filter -> Vector repeat dedupe -> Kafka ->
Sensor rate limit -> Workflow semaphore -> 24-hour incident claim -> ticket
```

## 1. Collection scope: Alloy

Alloy collects only the approved system or application namespace list. In the
two-lane design it labels every record `triage_scope=system` or
`triage_scope=application`. This is ownership segregation, not a volume brake:
Alloy still reads all logs/events in its assigned namespaces.

## 2. Admission: Vector tier filter

Vector is the first signal-quality brake. Each tier's
`transforms.incident_signals.condition` determines what reaches Kafka:

| Tier | Logs | Kubernetes events |
|---|---|---|
| 1 | fatal, panic, critical, OOM, segfault | OOM, scheduling, eviction, node/sandbox failures |
| 2 | errors, exceptions, failures, timeout, unavailable, denied | Tier 1 plus mounts, image pulls and Unhealthy |
| 3 | warnings plus Tier 2 patterns | broad review reason list |

Move tiers only after a controlled smoke and capacity review.

## 3. Burst suppression: Vector delivery key

`suppress_exact_repeats` drops repeated records with the same `delivery_key`.
For events the key is stable pod identity plus reason, so a CrashLoop BackOff
burst does not trigger one workflow per repeated Event count. Log delivery keys
also include the redacted evidence line, so a materially different failure can
still pass.

Watch:

```text
vector_component_discarded_events_total{component_id="suppress_exact_repeats"}
vector_component_sent_events_total{component_id="kafka"}
```

## 4. Sensor rate limit

Each Sensor is limited to **5 workflow triggers per minute**. With separate
system/application log/event Sensors, this is a per-routing-path brake; it is
not a global total. Lower it during first work deployment if the agent backend
is small.

## 5. Workflow concurrency

The WorkflowTemplate uses a semaphore backed by the
`triage-workflow-concurrency` ConfigMap. The current key allows **5 concurrent
workflow instances**. Extra workflows wait rather than all calling the agent
and GitLab at once. In the segregated design, give
`system-agentic-triage` and `application-agentic-triage` separate semaphore
keys so one noisy lane cannot consume the other lane's slots.

## 6. Incident and ticket dedupe

The 24-hour claim ConfigMap uses `dedupe_key` (cluster, namespace, pod) to
correlate a log and an event for the same workload into one incident/ticket.
The GitLab fingerprint label is a second backstop if workflows race.

## 7. Housekeeping

`podGC: OnPodCompletion` removes completed Pods after five minutes. Workflow
TTL removes successful Workflow CRs after one hour and failed ones after one
day. This prevents the historical thousands-of-Pods/workflows accumulation.

## Promotion gate

Do not promote a tier just because Pods are Ready. Require all of:

1. no Alloy `sending queue is full` errors;
2. Vector produced-message metric advances;
3. dedupe discard rate is plausible, not zero during a repeated smoke;
4. scoped Sensor creates only the expected workflow; and
5. workflow count remains below the configured concurrency/rate limits.
