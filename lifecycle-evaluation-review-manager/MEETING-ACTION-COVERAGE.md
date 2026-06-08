# Meeting Action Coverage

This bundle covers the evaluation work items assigned after the planning
discussion.

| Assigned action | Covered by | Evidence the work agent must produce |
| --- | --- | --- |
| Prepare evaluation framework design document | `observability/agent-evals/README.md`, `observability/agent-evals/LIFECYCLE-EVALUATION.md`, `observability/agent-evals/OFFLINE-ONLINE-EVALUATION-DESIGN.md` | Link to the design docs and confirm the target workflow stages are represented. |
| Define offline and online evaluation designs | `observability/agent-evals/OFFLINE-ONLINE-EVALUATION-DESIGN.md`, `observability/agent-evals/EVALUATION-ROLLOUT-OPERATING-MODE.md` | Explain offline vs online in one paragraph and map each to non-prod/prod rollout. |
| Identify key evaluation metrics | `observability/agent-evals/EVAL-METRICS-ACCESS-CONTROL-DESIGN.md`, `observability/agent-evals/FLEET-DASHBOARD.md`, `observability/agent-evals/scripts/metrics.py` | List metric names and labels; show generated Prometheus text output. |
| Propose the architecture: inline versus separate evaluator | `ARCHITECTURE-DECISION.md`, `observability/agent-evals/ARGO-RUNTIME.md` | Confirm the selected pattern: separate reusable evaluator step, but inline/public-image runtime with ConfigMap-mounted scripts. |
| Define data storage and access model | `DATA-STORAGE-ACCESS-TRACEABILITY.md`, `observability/agent-evals/EVAL-METRICS-ACCESS-CONTROL-DESIGN.md` | Show where metrics, reports, lifecycle JSON, and raw evidence live; show RBAC boundaries. |
| Add audit retention and traceability design | `DATA-STORAGE-ACCESS-TRACEABILITY.md`, `observability/agent-evals/EVALUATION-ROLLOUT-OPERATING-MODE.md` | Show retention table, traceability fields, and ticket/audit linkage. |

## Short Answer For Stakeholders

Offline eval is the promotion and replay path. It scores golden cases,
captured runs, and sanitized replays without touching a live incident workflow.

Online eval is the runtime audit path. It scores a real Argo/kagent incident
workflow after A2A, HITL, remediation, verification, and GitLab ticket update.
It can start audit-only in production, then become a gate for write-capable
remediation and ticket closure.

Inline versus separate evaluator is not a binary choice here. The architecture
uses a separate reusable evaluator workflow step, but runs it with an inline
shell script on `alpine:3.19` and ConfigMap-mounted scorer files. That avoids
custom image build friction while keeping the evaluator reusable and separately
permissioned from remediation.
