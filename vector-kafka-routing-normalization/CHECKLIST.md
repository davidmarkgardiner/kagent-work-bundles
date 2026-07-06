# Vector Kafka Routing Normalization Checklist

| Check | Evidence | Status |
|---|---|---|
| Bundle verifier passes | `scripts/verify-bundle.sh` output | TODO |
| Environment/tool preflight complete | variable/tool names only, no values | TODO |
| Existing Vector located | namespace, deployment/release, image/tag | TODO |
| Existing Vector config source located | ConfigMap/GitOps path/Helm values, no secret values | TODO |
| Existing Vector Confluent secret refs located | secret names and keys only | TODO |
| Grafana MCP access verified | tool/API access or blocker | TODO |
| Manager/Grafana contact point verified | contact point name/UID, redacted settings | TODO |
| Safe Grafana test alert path agreed | rule/route plan or blocker | TODO |
| Grafana MCP test alert fires | alert rule name/UID and state | TODO |
| Contact point delivery verified | redacted contact point delivery evidence | TODO |
| Current Kafka topics discovered | raw and normalized topic names | TODO |
| Kafka credentials reviewed | least-privilege plan recorded | TODO |
| Vector manifests adapted | placeholder-safe diff/MR | TODO |
| Vector config validated | Vector validate or equivalent | TODO |
| Kubernetes dry run passes | server-side dry-run output | TODO |
| Vector rollout healthy | deployment ready, probe status | TODO |
| Raw event produce verified | topic, partition, offset | TODO |
| Normalized event consumed | topic, partition, offset | TODO |
| Normalized record preserves cluster | `cluster` is the real Grafana alert label/commonLabel, not `unknown` | TODO |
| Normalized record preserves event reason | `event_reason` and `reason` match the Grafana/Kubernetes event reason | TODO |
| Normalized record preserves rich context | `event_context`, `suggested_kubectl`, and `suggested_log_query` are present where the alert provided them | TODO |
| Actionable topic contains actionable records only | consumed sample set and rejected noise examples | TODO |
| Route-verification workflow succeeds | workflow name and parameters | TODO |
| Production triage workflow triggered | workflow name and phase | TODO |
| Argo sensor receives rich context | workflow parameter/payload includes `cluster`, `event_reason`, `event_context`, `suggested_kubectl`, and `suggested_log_query` | TODO |
| Kit/kagent analysis completed | workflow/agent evidence | TODO |
| GitLab ticket created | issue URL/ID, redacted if required | TODO |
| GitLab ticket includes rich context | ticket body includes `cluster`, `event_reason`, suggested kubectl, suggested log query, dashboard/runbook links where available | TODO |
| App route verified | target agent and route key | TODO |
| Platform route verified | target agent and route key | TODO |
| Security route verified | target agent and route key | TODO |
| Unknown-owner fallback verified | target agent and route key | TODO |
| Duplicate suppression verified | N raw records -> 1 normalized workflow | TODO |
| Duplicate suppression happens before Argo | N raw records -> 1 actionable record -> 1 workflow | TODO |
| Resolved-alert filtering verified | no actionable record and no workflow created | TODO |
| Ignored severity/label filtering verified | dropped/quarantined, no actionable record and no workflow | TODO |
| Malformed payload filtering verified | dropped/quarantined, no actionable record and no workflow | TODO |
| Quarantine/drop decision captured | discard, metric-only, or quarantine topic with Argo excluded | TODO |
| Existing webhook/proxy chain documented | sanitized current-state diagram and inventory | TODO |
| Clean chain proposed or verified | Kafka-first or Vector HTTP receiver target path | TODO |
| Auth options verified | OAuth/OIDC support and API-key fallback decision | TODO |
| OAuth decision captured | supported, blocked, or not available | TODO |
| API key fallback documented | SASL_SSL/SASL_PLAIN with least-privilege topic scope | TODO |
| Proxy service role understood | translation only, extra logic, or unknown | TODO |
| Proxy removal decision captured | remove, keep, or blocked | TODO |
| Rollback plan captured | how to restore the known-working path | TODO |
| Home-lab replication plan captured | compatibility demo and clean demo | TODO |
| Production workflow full-envelope plan | proposed workflow/Sensor contract | TODO |
| Automation allowlist defined | default-deny gate and approved cases | TODO |
| Metrics plan defined | route, dedupe, workflow, MTTA/MTTR | TODO |
| Replay procedure documented | offset reset/replay plan | TODO |
| Output sanitized | no secrets/private endpoints | TODO |
