# Reference

Local source patterns:

- `observability/agent-evals/README.md`
- `observability/agent-evals/OFFLINE-ONLINE-EVALUATION-DESIGN.md`
- `observability/agent-evals/EVALUATION-ROLLOUT-OPERATING-MODE.md`
- `observability/agent-evals/LIFECYCLE-EVALUATION.md`
- `observability/agent-evals/ARGO-RUNTIME.md`
- `observability/agent-evals/EVAL-METRICS-ACCESS-CONTROL-DESIGN.md`
- `observability/agent-evals/FLEET-DASHBOARD.md`
- `observability/agent-evals/offline-online-eval-design.html`
- `observability/agent-evals/scripts/score-lifecycle-run.py`
- `observability/agent-evals/scripts/metrics.py`
- `observability/agent-evals/lifecycle-cases/chaos-pod-delete.yaml`
- `observability/agent-evals/results/sample/lifecycle/`
- `observability/agent-evals/grafana/kagent-fleet-overview-dashboard.json`
- `observability/agent-evals/alerting/agent-eval-rules.yaml`
- `KAGENT-EVAL-LIFT-AND-SHIFT-HANDOFF.md`
- `KAGENT-EVAL-PR-REVIEW.md`

Keep deterministic hard gates authoritative. LLM-as-judge or semantic scoring
can be layered later, but it must not replace HITL, namespace, verification,
ticket/report, and leak checks.
