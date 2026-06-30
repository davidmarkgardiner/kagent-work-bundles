# Promotion Gate

Use this gate before enabling the workflow outside a controlled development or
test namespace.

## Minimum Bar

- [ ] Three successful gameday runs.
- [ ] At least one application scenario passed.
- [ ] At least one platform scenario passed.
- [ ] At least one networking or security scenario passed.
- [ ] Zero unsafe write actions before HITL approval.
- [ ] Vector dedupe verified.
- [ ] Raw replay verified for Kafka-first path, or direct HTTP limitation
      accepted in writing.
- [ ] Ticket quality contract accepted by SRE.
- [ ] Grafana dashboard live and readable by stakeholders.
- [ ] MTTA/MTTR and deflection tracking fields agreed.
- [ ] Rollback tested.
- [ ] Failure-mode tests reviewed.
- [ ] Kafka and Grafana credentials least-privilege.
- [ ] Production alert noise and repeat intervals reviewed.

## No-Go Conditions

- Missing rollback.
- Unclear route ownership.
- Write-capable remediation without HITL.
- Ticket target unavailable with no fallback artifact.
- Dashboard cannot distinguish fired, routed, suppressed, remediated, and
  escalated events.
- Any secret or private endpoint appears in public evidence.
