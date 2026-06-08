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
Workflow: lifecycle-eval-hook-example-sr5d5
Namespace: argo
Status: Succeeded
Progress: 3/3
Evaluator log: score=1.0 passed=true
```

Runtime files mounted from ConfigMap:

```text
collect-lifecycle-evidence.py
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
- `a2a/smart-triage-fanout-demo/workflow.yaml`
