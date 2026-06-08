# Home-Lab Verification Evidence

Date: 2026-06-08

This bundle was verified against a local home-lab Kubernetes context before handoff. The canonical evidence is in:

- `observability/agent-evals/HOMELAB-VERIFICATION-EVIDENCE.md`

## What Was Proven

- Offline scoring distinguishes passing and below-threshold lifecycle runs.
- Below-threshold lifecycle scoring exits non-zero.
- Metrics are exported through the independent metrics library, `observability/agent-evals/scripts/metrics.py`.
- Argo server-side dry-run accepts the evaluator Kustomize bundle.
- Argo server-side dry-run accepts the standalone lifecycle eval hook example.
- Argo server-side dry-run accepts the full smart-triage fanout workflow.
- The safe online hook workflow runs successfully in Argo using public image `alpine:3.19`.
- The negative online hook fails evaluation and continues to a review-route stub.
- All hook pods run as the dedicated `agent-lifecycle-eval` ServiceAccount.
- The online hook produces lifecycle JSON, Markdown summary, and Prometheus-style metrics.

## Key Evidence

Offline:

```text
score-agent-run.py crashloop-wrong-env-var: score=1.0 passed=true
score-lifecycle-run.py pod-crashloop-hitl-remediation: score=1.0 passed=true
score-lifecycle-run.py chaos-pod-delete-below-threshold: score=0.575 passed=false
```

Online:

```text
Workflow: lifecycle-eval-hook-example-jszv5
Namespace: argo
Status: Succeeded
Progress: 3/3
Evaluator log: score=1.0 passed=true
```

Negative online:

```text
Workflow: lifecycle-eval-hook-negative-example-qgm9x
Namespace: argo
Status: Succeeded
Evaluate lifecycle task: Error (exit code 1)
Evaluator log: score=0.218 passed=false
Evaluator log: REVIEW_MANAGER_ROUTE: created /work/output/review-route.json
Route log: EXPECTED_NEGATIVE_ONLINE_EVAL: evaluator task failed and review route continued
```

Runtime files mounted from ConfigMap:

```text
collect-lifecycle-evidence.py
route-lifecycle-review.py
score-lifecycle-run.py
summarize-agent-scores.py
metrics.py
pod-crashloop-hitl-remediation.yaml
chaos-pod-delete.yaml
```

## Issue Found During Verification

The first online hook attempt failed because the reusable evaluator was called through `templateRef`, but the ConfigMap volume was defined at the `WorkflowTemplate.spec` level. The caller workflow did not inherit that volume.

Fix applied:

- Put the `agent-eval-runtime` ConfigMap volume on the reusable `evaluate-lifecycle` template.
- Use plain placeholder strings such as `PLACEHOLDER_GITLAB_ISSUE_ID` in runnable examples so Argo does not try to template unresolved GitLab values.
- Add dedicated evaluator RBAC with only Argo output-reporting permission.
- Add a negative online hook proving failed evidence gets a non-passing score
  and creates a review-route payload.

## Handoff Entry Points

Give the work agent these files first:

- `WORK-AGENT-START-PROMPT.md`
- `IMPLEMENTATION-VERIFY-PLAN.md`
- `HOMELAB-VERIFICATION-EVIDENCE.md`
- `payload/REFERENCE.md`
- `requests/lifecycle-evaluation-request.yaml`

Then ask it to implement or verify equivalent YAML from:

- `observability/agent-evals/kustomization.yaml`
- `observability/agent-evals/argo/lifecycle-eval-workflow-template.yaml`
- `observability/agent-evals/argo/lifecycle-eval-hook-example.yaml`
- `observability/agent-evals/argo/lifecycle-eval-hook-negative-example.yaml`
- `observability/agent-evals/argo/evaluator-rbac.yaml`
- `a2a/smart-triage-fanout-demo/workflow.yaml`
