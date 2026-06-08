# Lifecycle Evaluation Checklist

| Check | Evidence | Status |
|---|---|---|
| Work variables resolved first | `../SHARED-VARIABLES.md` mapping with placeholders kept out of repo | TODO |
| Bundle verifier passes | verifier output | TODO |
| Evaluation framework design covered | design doc links and summary | TODO |
| Offline eval design covered | offline flow summary and command | TODO |
| Online eval design covered | Argo flow summary and manifest path | TODO |
| Key metrics identified | metric names, labels, and generated output | TODO |
| Inline vs separate evaluator decision covered | architecture decision summary | TODO |
| Data storage/access model covered | data class/RBAC table | TODO |
| Audit retention/traceability covered | retention table and traceability fields | TODO |
| Eval cases loaded | case paths | TODO |
| Passing run scored | score output | TODO |
| Failing run scored | score output and exit code | TODO |
| Hard gates enforced | hard failure list | TODO |
| Review-manager route payload created | report/finding/issue payload | TODO |
| Chaos event flow mapped | event source/watch path and payload fields | TODO |
| Argo EventSource or watcher proven | event UID, workflow ID, logs, or exact blocker | TODO |
| Kagent triage run connected to event | triage run ID and input payload | TODO |
| Chaos lifecycle eval recorded | eval result for `chaos-pod-delete` or exact blocker | TODO |
| GitLab evidence updated | issue/MR/comment/report URL or exact blocker | TODO |
| Grafana alert path decision captured | `not_required_for_phase_1` or optional evidence URL | TODO |
| Metrics exported | Prometheus text or dashboard | TODO |
| Output sanitized | no secrets/private values in evidence | TODO |
