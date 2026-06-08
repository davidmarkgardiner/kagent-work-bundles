# Work-Agent Start Prompt

```text
You are the lifecycle evaluation and review-manager verifier.

Run:

bash scripts/verify-bundle.sh

This verifier uses the bundle-local `payload/agent-evals` copy of the scorer,
metrics library, route script, lifecycle cases, and sample runs. If you only
received this bundle directory, do not rely on `observability/agent-evals`
paths existing.

Then prove the work eval path:
1. Read FRONT-SHEET.md, CHECKLIST.md, MEETING-ACTION-COVERAGE.md,
   ARCHITECTURE-DECISION.md, DATA-STORAGE-ACCESS-TRACEABILITY.md,
   requests/*, prompts/*, payload/REFERENCE.md, and evidence/EVIDENCE-TEMPLATE.md.
2. Confirm the six planning-meeting actions are covered:
   evaluation framework design, offline/online designs, key metrics,
   inline-vs-separate architecture, data storage/access, audit retention and
   traceability.
3. Locate lifecycle eval cases, scorer, metrics library, Argo runtime template,
   dashboards, and alert rules.
4. Score one passing run.
5. Score one below-threshold or hard-failure run.
6. Confirm hard failures block closure and produce a review route payload.
7. Verify the independent metrics contract and label policy.
8. Define where lifecycle JSON, eval result JSON, Markdown reports, raw
   evidence, metrics, and trace identifiers are stored.
9. Route the failed run to review-manager or produce the review-manager ticket
   payload.
10. Return commands, scores, hard failures, metrics, storage/access decisions,
    traceability fields, and review artifact.
```
