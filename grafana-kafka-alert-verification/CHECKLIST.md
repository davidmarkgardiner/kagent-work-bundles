# Grafana Kafka Alert Verification Checklist

| Check | Evidence | Status |
|---|---|---|
| Bundle verifier passes | `scripts/verify-bundle.sh` output | TODO |
| Environment variables checked | variable names present/missing, no values | TODO |
| Grafana MCP/tools discovered | tool names or blocker | TODO |
| Kafka contact point verified | name/UID, redacted settings | TODO |
| Notification route verified | label matcher and contact point | TODO |
| Temporary firing alert created or found | alert rule name/UID | TODO |
| Alert observed firing | Grafana state and timestamp | TODO |
| Kafka record consumed | topic, partition, offset, timestamp | TODO |
| Raw payload captured | sanitized evidence file path | TODO |
| Draft schema validation run | pass/fail and schema delta | TODO |
| Resolved/OK payload captured or disabled | evidence or explicit setting | TODO |
| Argo examples reviewed | EventSource, Sensor, WorkflowTemplate adapted or rejected | TODO |
| Cluster-side consumer path proven | CLI, `kcat`, Argo Events, service, or bridge | TODO |
| Agent Gateway alert candidates validated | 429, 5xx, log-error, notification-failure queries | TODO |
| Broker schema decision recorded | consumer-side, bridge-required, or native-proven | TODO |
| Temporary Grafana smoke objects cleaned up | cleanup evidence | TODO |
| Output sanitized | no secrets/private endpoints | TODO |
