# Desired State: Evidence-First Worker Triage

The office pilot is green only when every required gate has direct evidence.
Static manifests, Ready pods or a created topic alone are not proof.

| ID | Desired state | Required evidence |
|---|---|---|
| DS-01 | Critique feedback accepted | Feedback file reviewed; named decisions/owners recorded. |
| DS-02 | Worker collection is read-only and scoped | Alloy identity/RBAC and explicit non-production namespace scope. |
| DS-03 | Worker Vector is fleet-grade | HA, PDB, topology spread, disk buffer, delivery policy and buffer-full loss metric. |
| DS-04 | Fingerprint is stable/discriminating | Workload+signature key; pod churn one incident, distinct signatures differ, node events have a class. |
| DS-05 | Envelope is safely redacted | Versioned secrets/PII pack, per-line/total cap and sampled scanner. |
| DS-06 | Tainted evidence is safe | File/artifact data path, agent delimiters and ticket scrub resist log/prompt injection. |
| DS-07 | Management validates/quarantines | Version/size/topic-to-cluster checks; bad records go to DLQ with counter and replay runbook. |
| DS-08 | Schema migration is safe | Accepted-major list, v2/v3 migration order and unknown-major quarantine proof. |
| DS-09 | Idempotency survives failure | Atomic TTL store, retry, failed/released claim state and unresolved-claim alert. |
| DS-10 | Delivery/burst behaviour is proven | Kafka→EventBus→Sensor contract, overflow observation, burst game-day and bounded workflow concurrency. |
| DS-11 | Ticket lifecycle is idempotent | Update open ticket; retry after post-create failure; long-lived incident is not re-ticketed daily. |
| DS-12 | Replay is safe | In-window, group-name/oldest and stale replay tests; stale input quarantined. |
| DS-13 | Kafka identity/outage recovery is isolated | Identity/ACL, cross-check, broker buffer/drain and loss accounting. |
| DS-14 | Agent is read-only/protected | Tool inventory, quotas/concurrency and model/A2A circuit breaker. |
| DS-15 | Log/event paths complete | Controlled log/event reach triage/ticket; ticket labels cross-reference expected human metric-page co-occurrence. |
| DS-16 | Human alerting/rollback are safe | Alertmanager unchanged; disable evidence route and retain human paging. |

## Verdict format

```text
EVIDENCE_FIRST_WORKER_TRIAGE_VERDICT: green|amber|red
GREEN_GATES: <count>/16
AMBER_GATES: <comma-separated IDs or none>
RED_GATES: <comma-separated IDs or none>
NEXT_OWNER: <role>
NEXT_ACTION: <one concrete action>
OUTPUT_SANITIZED: yes
```

`green` requires DS-01 through DS-16. `amber` means a bounded pilot may
continue only with named owner, expiry and compensating control. `red` means
do not onboard another worker cluster.
