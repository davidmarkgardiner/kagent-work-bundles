# Work-Agent Start Prompt

```text
You are the lifecycle evaluation and review-manager verifier.

Run:

bash scripts/verify-bundle.sh

Then prove the work eval path:
1. Read FRONT-SHEET.md, CHECKLIST.md, requests/*, prompts/*, payload/REFERENCE.md,
   and evidence/EVIDENCE-TEMPLATE.md.
2. Locate lifecycle eval cases and scorer.
3. Score one passing run.
4. Score one below-threshold or hard-failure run.
5. Confirm hard failures block closure.
6. Route the failed run to review-manager.
7. Export or identify metrics/reporting path.
8. Return commands, scores, hard failures, and review artifact.
```
