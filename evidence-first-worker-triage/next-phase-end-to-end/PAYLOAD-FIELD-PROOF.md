# Payload Field Proof — what the agent actually receives

**Question this answers:** when a log OR an event fires, does the envelope that
reaches the Argo workflow (and the kagent agent) carry enough to isolate and fix
fast — cluster, message type, the actual message, what the error is, pod,
service — or does the agent have to go dig?

**Short answer from the red proof:** most of it is carried and *proven* to reach
a real ticket. Two fields are missing and the work agent must add + prove them.

---

## Evidence we already captured

From `reference-config/VERIFICATION-2026-07-13.md` — both paths ran end to end
and produced real GitLab work items whose bodies carried the incident fields:

| Path | Fixture | Workflow | Reached agent | Ticket |
|---|---|---|---|---|
| **Log** | synthetic `ERROR` line, `payments-api-log-evidence-fixture` | `red-log-triage-9czb4` | `k8s-readonly-agent` | work item **#430** |
| **Event** | real Kubernetes `BackOff`, `checkout-api-evidence-fixture` | `red-event-triage-dd86g` | same agent | work item **#431** |

Captured source records (`observability/alloy-vector-kafka-triage/examples/crashloop-correlated.jsonl`):

```json
{"source_type":"pod-log","cluster":"{{CLUSTER_NAME}}","namespace":"payments","service":"checkout-api","pod":"checkout-api-abc","container":"checkout-api","message":"ERROR database authentication failed password=placeholder-credential"}
{"source_type":"kubernetes-event","cluster":"{{CLUSTER_NAME}}","namespace":"payments","service":"checkout-api","pod":"checkout-api-abc","container":"checkout-api","event_reason":"BackOff","message":"Back-off restarting failed container checkout-api"}
```

---

## The envelope contract (what Vector builds, what Argo forwards)

Source of truth: `reference-config/02-vector.yaml` (the `. = {…}` allow-list,
lines 53-67). Argo forwards `body` verbatim to the agent
(`03-argo.yaml` `diagnose-readonly`) and puts an allow-listed subset in the
ticket (`create-gitlab-issue` `safe_incident`).

| Field the agent gets | Set in Vector | Reaches agent? | In ticket? | Covers your ask |
|---|---|---|---|---|
| `cluster` | `.cluster` | ✅ | ✅ | **cluster name** ✅ |
| `signal_kind` (`log`/`event`) | `.signal_kind` | ✅ | ✅ | **message type** ✅ |
| `source_type` | `"opentelemetry"` | ✅ | ✅ | message type ✅ |
| `reason` | `.reason` (e.g. `BackOff`, `OOMKilled`, `FailedScheduling`) | ✅ | ✅ | **what the error is about** ✅ |
| `evidence.event_summary` | `.reason` | ✅ | ✅ | what it's about ✅ |
| `evidence.representative_log_lines` | redacted+capped `message` | ✅ | ✅ | **the actual message** ✅ |
| `pod` | `.pod` | ✅ | ✅ | **pod name** ✅ |
| `service` | `.service` | ✅ | ✅ | **service** ✅ |
| `namespace` | `.namespace` | ✅ | ✅ | scope ✅ |
| `observed_timestamp` | `.timestamp` | ✅ | ✅ | when ✅ |
| `dedupe_key` / `delivery_key` | sha of cluster:ns:pod | ✅ | ✅ (fingerprint label) | correlation ✅ |
| `automation_allowed: false` | constant | ✅ | ✅ | read-only guard ✅ |

Reconstructed envelope for the captured BackOff event (what the allow-list
produces from the fixture above):

```json
{
  "schema_version": "observability.triage.v2",
  "cluster": "red",
  "namespace": "payments",
  "pod": "checkout-api-abc",
  "service": "checkout-api",
  "reason": "BackOff",
  "signal_kind": "event",
  "source_type": "opentelemetry",
  "observed_timestamp": "2026-07-13T…Z",
  "dedupe_key": "<sha256 red:payments:checkout-api-abc>",
  "delivery_key": "<sha256 …>",
  "automation_allowed": false,
  "evidence": {
    "event_summary": "BackOff",
    "representative_log_lines": "Back-off restarting failed container checkout-api"
  }
}
```

---

## Gaps — the work agent MUST add and prove these

Your ask specifically included "not only is it a critical error, but what's the
error about." Two fields needed for that are **not** in the current envelope:

1. **`severity` / `level` — MISSING.** There is no field that says
   critical vs warning. Severity is only *implied* by `reason` and by the
   `incident_signals` filter matching `error|exception|fatal`. The agent cannot
   rank or prioritise on it. **Add** an explicit `severity` derived from the
   event type / log level (e.g. `OOMKilled|FailedScheduling` → `critical`,
   `Unhealthy|BackOff` → `warning`, log `FATAL|ERROR` → `critical|error`).

2. **`container` — RESOLVED 2026-07-21 (this doc was wrong about why).**
   The earlier claim here — "the source record carries `container`
   (`checkout-api`) but the Vector allow-list drops it" — was **incorrect**. It
   was based on the fixture at
   `observability/alloy-vector-kafka-triage/examples/crashloop-correlated.jsonl`,
   a hand-written example, **not** captured Alloy output. A live raw capture
   (`evidence/ALLOY-EVENT-RAW-CAPTURE-2026-07-21.md`) proves the Alloy
   **event** path never produced a `container` field at all:
   `loki.source.kubernetes_events` with `log_format="json"` emits a flattened
   body with no `involvedObject` and no `container`; the container name exists
   only inside `msg` text. There was never a `.container` for the allow-list to
   drop.
   - **Log path:** container was always present (Alloy label
     `__meta_kubernetes_pod_container_name`) — proven, e.g. ticket #500.
   - **Event path:** container is now parsed from `event.msg` in Vector
     (`02-vector.yaml` `normalize`), mirroring the existing `.pod = event.name`
     rescue — proven on ticket **#508** (`Container | the-failing-container`).
     Best-effort by design: `msg` names the container for crashloop-class
     events (`BackOff`, container-kill); probe (`Unhealthy`) and pod-scoped
     (`FailedScheduling`, `Evicted`) events do not name one and stay empty.

3. **`service` — log-path only, out of scope for events (decision 2026-07-21).**
   The pod-log path carries `service` from the `app.kubernetes.io/name` label.
   The k8s-event body has no equivalent, and the container/pod identity is what
   triage needs — so an empty `service` on an event ticket is **accepted, not a
   gap**. Do not chase it.

Optional enrichment worth proving at the same time: for the **log** path,
`.reason` defaults to the generic `log-error-signature`; the real error class
(auth failure, OOM, timeout) lives only inside `representative_log_lines`.
Consider extracting a `log_signature` so `reason` is specific for logs too.

---

## What the work agent must do (ties into Phase 1 + Phase 4)

```text
For BOTH a fired application log AND a fired Kubernetes event, capture the
envelope as it reaches the Argo workflow and prove EVERY required field is
present and correct, not empty/"unknown":
  cluster, signal_kind (message type), reason + evidence (what the error is),
  representative_log_lines (the actual message, redacted), pod, service,
  namespace, observed_timestamp, severity, container.
Add the missing severity and container fields to the Vector allow-list and the
Argo ticket allow-list, re-run both fixtures, and attach the two resulting
tickets (like #430 log / #431 event) showing the fields in the body. A field
that is "unknown" or absent is a fail: fix the mapping, do not ship the gap.
```

## Done when

```text
FIELD_CLUSTER_PRESENT: yes
FIELD_MESSAGE_TYPE_PRESENT: yes        # signal_kind + source_type
FIELD_ACTUAL_MESSAGE_PRESENT: yes      # evidence.representative_log_lines, redacted
FIELD_REASON_WHAT_ERROR_PRESENT: yes   # reason + event_summary
FIELD_POD_PRESENT: yes
FIELD_SERVICE_PRESENT: log-path-only    # events carry no service label — accepted, not a gap
FIELD_NAMESPACE_PRESENT: yes
FIELD_TIMESTAMP_PRESENT: yes
FIELD_SEVERITY_ADDED_AND_PRESENT: yes   # was missing — added
FIELD_CONTAINER_PRESENT: yes            # log: Alloy label; event: parsed from msg (#508)
# Reach-back fields added 2026-07-21 so a MANAGEMENT-cluster agent (which cannot
# live-inspect the worker) has every locator. Proven end-to-end on ticket #512.
FIELD_NODE_PRESENT: yes                 # event: sourcehost; log: Alloy node label
FIELD_OBJECT_KIND_PRESENT: yes          # event only (e.g. Pod); n/a for logs
FIELD_EVENT_COUNT_PRESENT: yes          # event only; 0 for logs
FIELD_REPORTING_COMPONENT_PRESENT: yes  # event only (e.g. kubelet); n/a for logs
TICKET_HAS_REACHBACK_KUBECTL: yes       # copy-paste describe/logs/get-events block
TICKET_LABELS_EVENT_VS_LOG_MESSAGE: yes # "Event message" / "Log error message"
BOTH_SIGNALS_ONE_TICKET: yes            # log + correlated event in one issue (#512)
REDACTION_IN_FINAL_TICKET: yes          # password/token redacted, useful text kept (#512)
NO_FIELD_UNKNOWN_OR_EMPTY: yes
PROVEN_ON_LOG_AND_EVENT_TICKET: yes    # a ticket per path, fields visible
OUTPUT_SANITIZED: yes
```
