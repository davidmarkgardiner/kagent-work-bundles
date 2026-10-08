# Triage payload and Kafka admission

The assessor runs every hour over the preceding hour. It creates and validates a
`namespace-health.report.v1` report for every run, but publishes to the triage
Kafka topic **only** when `status == investigate` and at least one namespace
meets the configured threshold. A quiet run produces a structured local Job log
and no Kafka record. A run with incomplete required coverage and no positive
finding produces no Kafka record and fails the Job so operational monitoring
can alert on the missing assessment. A positive finding with partial coverage
still publishes; `coverage.required_failed` remains true in its payload.

## Value sent to Kafka

The Kafka key is `slot_id`. The value is the complete canonical JSON report,
bounded to 8 KiB and validated against `report.schema.json`. The fields an
eventual triage agent needs are:

| Field | Use |
| --- | --- |
| `schema`, `cluster`, `source_generation`, `policy_version` | Select the correct parser and trusted source policy. |
| `slot_id`, `scheduled_at`, `window_started_at` | Deduplicate and describe the evidence window. |
| `status`, `threshold`, `automation_allowed` | Confirm admission; `automation_allowed` is always false. |
| `namespaces[]` | At most three selected namespaces, each with a risk tier and up to three named findings. |
| `namespaces[].findings[]` | Rule ID, risk tier, observed count, and up to three typed workload references. Lower-tier context can accompany a qualifying namespace; it did not independently trigger admission. |
| `coverage`, `qualifying_namespaces_omitted` | Tell the agent what was sampled, missing, or left out. |
| `finding_digest`, `payload_digest` | Detect repeated findings and exact payload changes. |

No raw Pod log line or Kubernetes Event message is sent. The current warning
Event rule contributes a count and a generic `Event/typed-warning` reference;
it does **not** provide an Event reason, involved object, or message. Before an
agent is asked to diagnose from this payload alone, define and test a bounded,
redacted Event evidence summary or give the read-only agent a scoped follow-up
tool. Do not claim the current payload is a complete diagnostic bundle.

## Argo intake boundary

The Argo EventSource uses `jsonBody: true`. Its Sensor checks
`body.schema == namespace-health.report.v1`, `body.status == investigate`, and
the expected `body.cluster`. It copies the **whole `body` JSON object** into a
Workflow `report` parameter. The current receipt container reads `REPORT_JSON`,
validates the complete report, checks source generation and slot identity, and
atomically claims the first valid finding for that slot. This is the present
endpoint; it does not call an agent.

When an agent handoff is built, parse and validate that same JSON inside a
dedicated adapter, then construct a bounded agent input from the selected
namespaces, findings, window, and coverage fields above. Never pass an
unvalidated Sensor field directly into a prompt or grant the receipt workflow
remediation permissions. Repeated identical findings need a separate cooldown
before any model call.

## Operational monitoring after quiet suppression

The historical direct-Kafka monitor assumed one record per scheduled hour.
It cannot be used for missing-slot detection on this selective topic: no
record now means either a quiet hour or a failed run. Before unsuspending the
workplace pilot, arrange monitoring independent of the triage topic for
CronJob schedule/Job completion, failed Jobs (including `unknown` coverage),
and assessor logs or equivalent metrics. Demonstrate a missed schedule and a
required-coverage failure. The direct-Kafka monitor can still inspect
published investigation reports and broker reachability, but its missing-slot
alarm must be disabled for a selective topic.

The October 7 home-lab evidence and image inventory describe the earlier
all-status publisher. This selective-admission change is source-only until a
new image, target render, and live canary are built and verified.
