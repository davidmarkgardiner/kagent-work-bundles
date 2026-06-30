# Prompt 04: Production Readiness Gap Check

Before production, verify or block the following.

Required for production:

1. Production triage workflow consumes the full normalized envelope, not just
   `body.alertmanager`.
2. Write-capable automation remains default-deny.
3. Argo has an explicit allowlist for approved remediation cases.
4. Kafka credentials are split by least privilege.
5. Raw topic retention and replay procedure are documented.
6. Metrics exist or are planned for route counts, suppression, workflow
   outcomes, MTTA, MTTR, and escalation/deflection.
7. Vector restart behavior and dedupe limitations are documented.
8. Old raw-topic Sensor is disabled, narrowed, or documented as replay/debug
   only.

Return:

```text
FULL_ENVELOPE_WORKFLOW: planned_or_implemented
AUTOMATION_GATE: default_deny
KAFKA_PRINCIPALS: split_or_gap
REPLAY_PLAN: documented_or_gap
METRICS_PLAN: captured_or_gap
RAW_SENSOR_STEADY_STATE: disabled_narrowed_or_gap
PRODUCTION_GO_NO_GO: GO | NO_GO
BLOCKERS:
NEXT_ACTION:
```
