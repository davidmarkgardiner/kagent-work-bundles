# Failure-Mode Tests

Run these before promoting the flow beyond a test namespace. They prove the
platform fails predictably instead of silently losing incidents.

| Test | Expected behavior |
|---|---|
| Vector down in Kafka-first path | Raw event remains in Kafka; Vector catches up after recovery. |
| Vector down in direct HTTP path | Alert delivery fails or retries according to contact point policy; no claim of raw replay. |
| Kafka normalized topic unavailable | Vector logs produce failure; Argo does not create false workflow success. |
| Duplicate alert burst | Vector emits one normalized workflow event per dedupe window. |
| Resolved alert | Vector filters or routes as resolution-only; no new remediation workflow. |
| Wrong route label | Event goes to fallback route or is rejected with evidence. |
| Specialist agent unavailable | Workflow records blocked specialist call and creates/updates ticket with blocker. |
| GitLab/ServiceNow unavailable | Workflow records ticket failure and keeps evidence artifact. |
| HITL timeout | Workflow stops before write-capable action and records timeout. |
| Dashboard missing data | Run is marked partial; no stakeholder success claim. |

## Evidence Markers

```text
FAIL_VECTOR_DOWN: verified_or_blocked
FAIL_KAFKA_TOPIC: verified_or_blocked
FAIL_DUPLICATE_BURST: verified_or_blocked
FAIL_RESOLVED_ALERT: verified_or_blocked
FAIL_WRONG_ROUTE: verified_or_blocked
FAIL_AGENT_UNAVAILABLE: verified_or_blocked
FAIL_TICKET_TARGET_UNAVAILABLE: verified_or_blocked
FAIL_HITL_TIMEOUT: verified_or_blocked
FAIL_DASHBOARD_MISSING_DATA: verified_or_blocked
```

Any failed safety test blocks production promotion.
