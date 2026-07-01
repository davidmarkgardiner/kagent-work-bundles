# Prompt 03: Verify Routing And Dedupe

Send synthetic, non-production route-test events through the raw Kafka topic.
They must include a marker such as:

```json
{ "routing_test": true }
```

Verify these routes:

| Case | Expected |
|---|---|
| app namespace + service | application/SRE triage agent |
| platform namespace or pod event | platform ops agent |
| security namespace/advisory | security hardening agent |
| missing service owner | fallback SRE triage agent |

Verify dedupe:

1. Send the same raw payload three times.
2. Confirm only one actionable Kafka record is produced inside the dedupe
   window.
3. Confirm only one normalized route workflow is created.

Verify filtering:

1. Send a resolved Alertmanager alert.
2. Send a resolved Grafana alert.
3. Send an ignored severity payload if the work policy has ignored severities.
4. Send an ignored namespace/service payload if the work policy has ignored
   owners or namespaces.
5. Send a malformed or incomplete payload.
6. Confirm none of these create an actionable Kafka record.
7. Confirm none of these create a normalized route workflow.
8. Confirm dropped/noisy events are either counted in Vector metrics or written
   to a quarantine topic that Argo does not consume.

Verify the normalized/actionable schema includes:

```text
schema_version
source_system
alert_uid
fingerprint
status
severity
namespace
service
owner
target_agent
route_domain
route_key
routing_reason
dedupe_key
incident_candidate
automation_allowed
raw_event_ref_or_hash
```

The actionable topic should be safe for Argo to consume directly. If extra
filtering is still required in Argo, record it as a gap and propose how Vector
will absorb that logic.

Return:

```text
RAW_KAFKA_RECORD: produced
NORMALIZED_KAFKA_RECORD: consumed
ACTIONABLE_TOPIC_CLEAN: verified
ROUTE_APP: verified
ROUTE_PLATFORM: verified
ROUTE_SECURITY: verified
ROUTE_FALLBACK: verified
DEDUPE: verified
RESOLVED_FILTER: verified
NOISE_FILTER: verified
MALFORMED_PAYLOAD_FILTER: verified
QUARANTINE_DECISION: discard_metric_or_topic
ARGO_EXTRA_FILTERING_REQUIRED: yes_or_no
WORKFLOW_NAMES:
ROUTE_KEYS:
DEDUPE_KEYS:
ACTIONABLE_TOPIC_OFFSETS:
QUARANTINE_TOPIC_OFFSETS:
NEXT_ACTION:
```
