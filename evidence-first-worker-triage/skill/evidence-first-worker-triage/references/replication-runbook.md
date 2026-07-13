# Replication Runbook

Use this map after reading the skill. It makes the handover reproducible while
keeping all environment-specific values outside the bundle.

## Implementation map

| Stage | Configure in the target | Required outcome | Proof |
|---|---|---|---|
| Collect | Existing worker Alloy release | One approved namespace; pod logs and Warning events carry source metadata | Alloy status plus a controlled log and event at Vector input |
| Process | Existing worker-local Vector deployment | Allow-listed v3 envelope, redaction/caps, stable fingerprint, burst control, persistent buffer | Vector config validation, metrics and redacted Kafka record |
| Transport | Existing Confluent topic/identity | SASL or mTLS, topic ACL only, key=`incident_fingerprint` | Produce/consume check and broker outage/drain result |
| Validate | Management Kafka consumer before Argo trigger | Version, source, timestamp and size checks; DLQ/quarantine | Valid record accepted; invalid version quarantined |
| Claim | Approved durable TTL store in management | Atomic 24h claim, release/retry, expiry takeover | Same input/replay and post-create failure test |
| Orchestrate | Existing EventSource, Sensor, EventBus and Workflow | Bounded concurrency, evidence parameter forwarded unchanged | Workflow shows correct payload and rate-limit behaviour |
| Diagnose | Existing `k8s-readonly-agent`/A2A binding | Read-only tools only; untrusted data cannot instruct agent | Tool inventory and workflow diagnosis output |
| Ticket | Existing GitLab integration | Create/update by fingerprint; independently scrubbed content | One issue per incident and retry/update proof |

## Source patterns to adapt

These public, sanitized patterns are the canonical starting points when the
agent is working in the kagent repository. Inspect them before designing a
replacement; do not copy the red overlay directly into an office environment.

| Need | Source pattern | Adaptation required |
|---|---|---|
| Alloy collection | `observability/alloy-vector-kafka-triage/01-alloy-config.yaml` | Merge components into the existing Alloy release and scope discovery to the pilot namespace. |
| Vector normalisation | `observability/alloy-vector-kafka-triage/02-vector.yaml` | Replace proof-only in-memory dedupe with workload/signature fingerprinting and approved disk-buffer delivery controls. |
| Red proof behaviour | `observability/alloy-vector-kafka-triage/red/` | Use only to understand a proven log/event-to-ticket path; remove its proof-only ConfigMap claim and single-cluster assumptions. |
| Kafka EventSource/Sensor | `observability/alloy-vector-kafka-triage/03-argo-triage.yaml` | Bind existing Confluent secret/CA references; add validation, DLQ and management-only consumer ownership. |
| Confluent source baseline | `observability/confluent-cloud-pipeline/management-cluster/01-eventsource-confluent.yaml` | Preserve approved endpoint and credential references; never copy secrets. |
| kagent triage integration | `agents/kagent-triage/02-workflow-kagent-triage.yaml` | Retain a read-only agent and evidence-as-untrusted-data prompt boundary. |

If the repository is not available alongside the downloaded bundle, ask the
owner for the approved existing Alloy, Vector, Argo and kagent overlays. Do
not fabricate replacement production manifests from this runbook.

## Envelope contract

The management consumer must accept only an allow-listed JSON envelope. Keep
the schema versioned and reject unknown major versions.

```json
{
  "schema_version": "observability.triage.v3",
  "incident_fingerprint": "sha256-of-stable-workload-and-signature",
  "delivery_key": "sha256-of-exact-observation",
  "cluster": "approved-worker-cluster-id",
  "environment": "non-production",
  "namespace": "approved-namespace",
  "workload": "deployment-or-node-class",
  "pod": "optional-ephemeral-observation-context",
  "container": "optional-container",
  "signal_kind": "log|event",
  "reason": "normalised-reason",
  "observed_at": "RFC3339 UTC timestamp",
  "severity": "warning|critical",
  "evidence": {
    "summary": "redacted and capped",
    "representative_lines": ["redacted and capped"],
    "event_fields": {"allow-listed": "only"}
  },
  "automation_allowed": false
}
```

Do not include raw Kubernetes object dumps, bearer tokens, cookies, headers,
credentials, unrestricted labels/annotations, or agent instructions. The
agent may receive this envelope and then request read-only Kubernetes details.

## Control-to-proof matrix

| Control | Minimum passing test |
|---|---|
| Redaction and caps | Inject known fake secret and overlong line; neither is present in Kafka, workflow or ticket. |
| Fingerprint | Pod restart preserves incident fingerprint; distinct error signatures differ; node event uses node class. |
| Vector delivery | Broker unavailable produces buffer/lag metric; recovery drains without unbounded replay. |
| Validation/DLQ | Bad schema, oversize record and unexpected cluster are quarantined with an observable counter. |
| TTL idempotency | Concurrent same fingerprint produces one claim; ticket API succeeds then workflow fails; retry updates same issue. |
| Replay | In-window duplicate is suppressed, stale record quarantined, new consumer group does not recreate an open incident. |
| Read-only agent | Tool list includes only diagnostic tools; no mutation or exec call is possible. |
| Rollback | Disable new worker route and management consumer; existing human alerting remains unchanged. |

## Expected handover outputs

1. Private values-file location and discovered existing-resource inventory,
   without values in Git or chat.
2. Committed/additive target overlays and any approved durable-store or DLQ
   resources.
3. Server-side dry-run and live readiness evidence.
4. An evidence index for DS-01 through DS-16, containing redacted command
   output, workflow references and GitLab issue URLs/IDs where authorised.
5. The exact green/amber/red verdict and named next owner/action.
