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
2. Confirm only one normalized route workflow is created.

Verify filtering:

1. Send a resolved Alertmanager alert.
2. Send a resolved Grafana alert.
3. Confirm neither creates a normalized route workflow.

Return:

```text
RAW_KAFKA_RECORD: produced
NORMALIZED_KAFKA_RECORD: consumed
ROUTE_APP: verified
ROUTE_PLATFORM: verified
ROUTE_SECURITY: verified
ROUTE_FALLBACK: verified
DEDUPE: verified
RESOLVED_FILTER: verified
WORKFLOW_NAMES:
ROUTE_KEYS:
DEDUPE_KEYS:
NEXT_ACTION:
```
