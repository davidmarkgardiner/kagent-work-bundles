# Reference

Bundle-local runnable payload:

- `payload/agent-evals/scripts/score-lifecycle-run.py`
- `payload/agent-evals/scripts/route-lifecycle-review.py`
- `payload/agent-evals/scripts/summarize-agent-scores.py`
- `payload/agent-evals/scripts/metrics.py`
- `payload/agent-evals/lifecycle-cases/pod-crashloop-hitl-remediation.yaml`
- `payload/agent-evals/lifecycle-cases/chaos-pod-delete.yaml`
- `payload/agent-evals/results/sample/lifecycle/`

Full-repo source patterns:

- `observability/agent-evals/README.md`
- `observability/agent-evals/OFFLINE-ONLINE-EVALUATION-DESIGN.md`
- `observability/agent-evals/EVALUATION-ROLLOUT-OPERATING-MODE.md`
- `observability/agent-evals/LIFECYCLE-EVALUATION.md`
- `observability/agent-evals/ARGO-RUNTIME.md`
- `observability/agent-evals/EVAL-METRICS-ACCESS-CONTROL-DESIGN.md`
- `observability/agent-evals/FLEET-DASHBOARD.md`
- `observability/agent-evals/HOMELAB-VERIFICATION-EVIDENCE.md`
- `observability/agent-evals/offline-online-eval-design.html`
- `observability/agent-evals/argo/evaluator-rbac.yaml`
- `observability/agent-evals/argo/lifecycle-eval-workflow-template.yaml`
- `observability/agent-evals/argo/lifecycle-eval-hook-example.yaml`
- `observability/agent-evals/argo/lifecycle-eval-hook-negative-example.yaml`
- `observability/agent-evals/scripts/score-lifecycle-run.py`
- `observability/agent-evals/scripts/collect-lifecycle-evidence.py`
- `observability/agent-evals/scripts/route-lifecycle-review.py`
- `observability/agent-evals/scripts/metrics.py`
- `observability/agent-evals/lifecycle-cases/chaos-pod-delete.yaml`
- `observability/agent-evals/results/sample/lifecycle/`
- `observability/agent-evals/grafana/kagent-fleet-overview-dashboard.json`
- `observability/agent-evals/alerting/agent-eval-rules.yaml`
- `KAGENT-EVAL-LIFT-AND-SHIFT-HANDOFF.md`
- `KAGENT-EVAL-PR-REVIEW.md`
- `work-agent-bundles/lifecycle-evaluation-review-manager/HOMELAB-VERIFICATION-EVIDENCE.md`

Chaos-event-to-evaluation source patterns:

- `work-agent-bundles/chaos-reliability-remediation/examples/chaos-test-pod-delete.yaml`
- `work-agent-bundles/chaos-reliability-remediation/examples/argo-workflow-dry-run.yaml`
- `work-agent-bundles/chaos-reliability-remediation/examples/a2a-chaos-request-payload.json`
- `platform/argo-workflows/templates/chaos-test-lifecycle.yaml`
- `chaos/litmus/manifests/eventsource-litmus.yaml`
- `chaos/litmus/manifests/sensor-litmus-triage.yaml`

Keep deterministic hard gates authoritative. LLM-as-judge or semantic scoring
can be layered later, but it must not replace HITL, namespace, verification,
ticket/report, and leak checks.
