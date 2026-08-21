# Source-Aware Payload and Ticket Amendment

Use this amendment when replicating the evidence-triage path at work. It keeps
the Kafka payload, Argo workflow and GitLab ticket truthful: a field is passed
only when it is present in the source or is required by downstream routing,
deduplication, investigation or evaluation.

This is deliberately an **adapt-and-prove** example, not a manifest to apply
verbatim. Validate the VRL against the pinned Vector image and the Argo/JQ
rendering against representative payloads before promotion.

## Why this amendment exists

There are two different current patterns in the repo:

- The lean worker pilot envelope in `kustomize/base/worker.yaml` does not add
  `container` or `service`.
- The richer proof envelope in
  `next-phase-end-to-end/reference-config/02-vector.yaml` always serialises
  `container` and `service`, even when the event source has no value. Its
  corresponding renderer in `applied-config/03-argo-augmented.yaml` always
  prints those rows.

Raw Kubernetes events do not reliably contain a service label and some events
do not name a container. Empty strings, `unknown` and `n/a` are not evidence;
do not send or render them merely to make log and event tickets look alike.

## Contract rule

| Source | Required evidence contract | Conditional fields | Do not send/render |
|---|---|---|---|
| Pod/application log | cluster, namespace, workload/pod, reason/signature, severity, observed timestamp, bounded redacted log evidence | `container`, `service` only if Alloy/OTLP actually supplied them | empty/default identity fields |
| Kubernetes Warning event | cluster, namespace, object kind/name, reason, severity, event type/count, observed timestamp, bounded redacted event evidence | `container` only if reliably parsed from the event message and validated; reporting controller/instance only if useful to the investigator | `service`, `container` or log-only fields when absent |

All fields used to calculate an incident/delivery key must remain available
until the key is calculated. Do not use an empty `service` or a literal pod
name as a permanent incident identity; use the approved stable workload
identity after it has been proven to exist for both log and event paths.

## Vector VRL pattern

Build the common envelope first. Add source-specific keys only when their value
is non-empty and evidence-backed:

```vrl
# Earlier in the transform: derive and redact these values from the source.
# container and service use "" when absent; never turn absence into "unknown".

. = {
  "schema_version": "observability.triage.v{{VERSION}}",
  "cluster": cluster,
  "namespace": namespace,
  "workload": workload,
  "reason": reason,
  "severity": severity,
  "signal_kind": signal_kind,
  "observed_timestamp": to_string(.timestamp) ?? "",
  "incident_fingerprint": incident_fingerprint,
  "delivery_key": delivery_key,
  "automation_allowed": false,
  "evidence": evidence
}

if signal_kind == "log" {
  if container != "" { .container = container }
  if service != "" { .service = service }
}

if signal_kind == "event" {
  if object_kind != "" { .object_kind = object_kind }
  if event_count > 0 { .event_count = event_count }
  if reporting_controller != "" { .reporting_controller = reporting_controller }
  # Add .container only if an explicit event-message parse found a real value.
  if container != "" { .container = container }
}
```

Do not use `container = "unknown"` or `service = "unknown"` before this
block: that converts absence into a misleading transmitted value. Redact and
bound `evidence` before assigning the final envelope, as in the existing
Vector transform.

## Argo behaviour

The EventSource and Sensor should validate only fields that are universal or
required for a particular route:

```text
all inputs: schema_version, automation_allowed, signal_kind, reason,
            incident_fingerprint, observed_timestamp, bounded evidence
log route:  log signature/evidence; optional container/service are not filters
event route: object kind/name, event reason/type/count where the policy needs them
```

Do not make a Sensor filter require `container` or `service` for Kubernetes
events. Its absence is normal and must not silently discard a valid warning.

## GitLab renderer pattern

Render common rows, then conditionally append optional rows. The following JQ
helper replaces unconditional `Container`/`Service` table rows:

```jq
def optional_row($label; $value):
  if $value == null or $value == "" or $value == "unknown" then
    ""
  else
    "| " + $label + " | `" + ($value | tostring) + "` |\n"
  end;

"### Incident contract\n" +
"| Field | Value |\n|---|---|\n" +
"| Cluster | `" + $i.cluster + "` |\n" +
"| Namespace | `" + $i.namespace + "` |\n" +
"| Workload / Pod | `" + $i.workload + "` |\n" +
optional_row("Container"; $i.container) +
optional_row("Service"; $i.service) +
optional_row("Object kind"; $i.object_kind) +
optional_row("Event count"; $i.event_count) +
"| Reason | `" + $i.reason + "` |\n" +
"| Severity | " + $i.severity + " |\n" +
"| Signal kind | " + $i.signal_kind + " |\n"
```

Use the same helper for correlated-evidence notes. A work-cluster ticket should
show a missing field only when that absence is itself diagnostic, and then say
why in the diagnosis—not as a synthetic contract value.

## Payload examples and assertions

### Log payload — captured identity is present

```json
{
  "signal_kind": "log",
  "cluster": "{{WORKER_CLUSTER}}",
  "namespace": "{{TEST_NAMESPACE}}",
  "workload": "{{WORKLOAD}}",
  "container": "{{CONTAINER}}",
  "service": "{{SERVICE}}",
  "reason": "log-error-signature",
  "severity": "error",
  "evidence": {"summary": "ERROR {{SAFE_TEST_MARKER}} [REDACTED]"}
}
```

```bash
jq -e '
  .signal_kind == "log" and
  (.container | type == "string" and length > 0) and
  (.service | type == "string" and length > 0) and
  (.evidence.summary | type == "string" and length > 0)
' {{LOG_PAYLOAD_JSON}}
```

### Event payload — absent log identity is omitted

```json
{
  "signal_kind": "event",
  "cluster": "{{WORKER_CLUSTER}}",
  "namespace": "{{TEST_NAMESPACE}}",
  "workload": "{{WORKLOAD_OR_OBJECT_NAME}}",
  "object_kind": "Pod",
  "reason": "BackOff",
  "severity": "warning",
  "event_count": 1,
  "evidence": {"summary": "Back-off restarting failed container {{CONTAINER}}"}
}
```

```bash
jq -e '
  .signal_kind == "event" and
  (.object_kind | type == "string" and length > 0) and
  (.reason | type == "string" and length > 0) and
  (has("service") | not) and
  ((has("container") | not) or (.container | type == "string" and length > 0))
' {{EVENT_PAYLOAD_JSON}}
```

## Required proof before GitOps promotion

1. Run a controlled log and event fixture through Alloy -> Vector -> Kafka.
2. Capture the actual Kafka/EventSource body for both, with sensitive values
   redacted.
3. Run the assertions above against the captured payloads.
4. Prove Argo accepts both payloads and creates the correct route/workflow.
5. Compare each GitLab ticket with
   `home-triage-gitlab-ticket-example.md`: no empty rows, no fabricated values,
   no raw sensitive evidence.
6. Add the payload fixtures and checks to the scheduled smoke/eval path only
   after this manual proof is green.

This amendment does not change the Kafka message schema version by itself. If
the target contract is already externally consumed, make the omission rule a
documented backward-compatible change and test every consumer before rollout.
