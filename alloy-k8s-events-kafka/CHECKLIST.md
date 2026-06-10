# Alloy Kubernetes Events To Kafka Checklist

| Check | Evidence | Status |
| --- | --- | --- |
| Environment preflight complete | set/missing only, no values | TODO |
| Namespace scope configured | `namespaces = ["{{TEST_NAMESPACE}}"]` | TODO |
| RBAC is read-only and namespace-bound | Role/RoleBinding in test namespace | TODO |
| Alloy Secret exists | Secret name only | TODO |
| Alloy Deployment ready | rollout status | TODO |
| Argo WorkflowTemplate applied | name and namespace | TODO |
| Argo EventSource ready | consumer group and topic | TODO |
| Argo Sensor ready | dependency and trigger | TODO |
| Smoke Event triggered | event reason/name | TODO |
| Alloy observed event | sanitized logs or metrics | TODO |
| Kafka record consumed | topic, partition, offset, timestamp | TODO |
| Argo consumed record | EventSource logs | TODO |
| Argo Sensor created Workflow | Workflow name | TODO |
| Payload captured | sanitized Workflow logs | TODO |
| Schema decision recorded | consumer-side/broker-side/blocker | TODO |
| Cleanup completed | smoke resources removed or retained by request | TODO |
| Output sanitized | no secrets/private endpoints | TODO |
