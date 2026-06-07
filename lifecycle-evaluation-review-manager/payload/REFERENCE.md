# Reference

Local source patterns:

- `observability/agent-evals/README.md`
- `observability/agent-evals/LIFECYCLE-EVALUATION.md`
- `observability/agent-evals/ARGO-RUNTIME.md`
- `observability/agent-evals/scripts/score-lifecycle-run.py`
- `observability/agent-evals/lifecycle-cases/chaos-pod-delete.yaml`
- `observability/agent-evals/results/sample/lifecycle/`
- `observability/agent-evals/grafana/kagent-fleet-overview-dashboard.json`

Keep deterministic hard gates authoritative. LLM-as-judge or semantic scoring
can be layered later, but it must not replace HITL, namespace, verification,
ticket/report, and leak checks.
