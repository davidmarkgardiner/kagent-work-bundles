# Prompt: Run Lifecycle Evaluation

```text
Run the lifecycle evaluator against one passing and one below-threshold case.
Return score, pass/fail state, hard failures, review-manager route, and metrics
or report output.

Also inspect recent eval-related workflow runs and report any failed historical
cases separately. Do not claim the eval path is healthy from one exported metric
or one old successful workflow.

Before running evidence commands, confirm the design coverage:

1. Evaluation framework design exists and points to the scorer, cases, reports,
   metrics, dashboard, alerts, and Argo runtime.
2. Offline eval is defined as CI/replay/golden-case scoring.
3. Online eval is defined as Argo post-run lifecycle scoring.
4. Metrics are identified and rendered through an independent library.
5. Architecture is selected: separate reusable evaluator step, inline public
   image runtime, ConfigMap-mounted scripts, no custom image required.
6. Data storage/access model is documented.
7. Audit retention and traceability fields are documented.

Minimum commands to adapt:

```bash
kubectl kustomize observability/agent-evals

python3 observability/agent-evals/scripts/score-lifecycle-run.py \
  --case observability/agent-evals/lifecycle-cases/pod-crashloop-hitl-remediation.yaml \
  --run observability/agent-evals/results/sample/lifecycle/pod-crashloop-hitl-remediation.lifecycle-run.json \
  --output-dir /tmp/kagent-lifecycle-evals-pass

python3 observability/agent-evals/scripts/score-lifecycle-run.py \
  --case observability/agent-evals/lifecycle-cases/chaos-pod-delete.yaml \
  --run observability/agent-evals/results/sample/lifecycle/chaos-pod-delete-below-threshold.lifecycle-run.json \
  --output-dir /tmp/kagent-lifecycle-evals-fail

python3 observability/agent-evals/scripts/summarize-agent-scores.py \
  --results-dir observability/agent-evals/results/sample \
  --summary-md /tmp/kagent-agent-eval-summary.md \
  --metrics /tmp/kagent-agent-eval.prom
```

Return the evidence using `evidence/EVIDENCE-TEMPLATE.md`.
```
