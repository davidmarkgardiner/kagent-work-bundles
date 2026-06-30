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
| Route-verification workflow succeeds | workflow name and parameters | TODO |
| Production triage workflow triggered | workflow name and phase | TODO |
| Kit/kagent analysis completed | workflow/agent evidence | TODO |
| GitLab ticket created | issue URL/ID, redacted if required | TODO |
| App route verified | target agent and route key | TODO |
| Platform route verified | target agent and route key | TODO |
| Security route verified | target agent and route key | TODO |
| Unknown-owner fallback verified | target agent and route key | TODO |
| Duplicate suppression verified | N raw records -> 1 normalized workflow | TODO |
| Resolved-alert filtering verified | no normalized workflow created | TODO |
| Production workflow full-envelope plan | proposed workflow/Sensor contract | TODO |
| Automation allowlist defined | default-deny gate and approved cases | TODO |
| Metrics plan defined | route, dedupe, workflow, MTTA/MTTR | TODO |
| Replay procedure documented | offset reset/replay plan | TODO |
| Output sanitized | no secrets/private endpoints | TODO |
