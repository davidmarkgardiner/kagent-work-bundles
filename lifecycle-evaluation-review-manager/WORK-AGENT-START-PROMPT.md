# Work-Agent Start Prompt

```text
You are the lifecycle evaluation and review-manager verifier.

Run:

bash scripts/verify-bundle.sh

Then prove the work eval path:
1. Locate lifecycle eval cases and scorer.
2. Score one passing run.
3. Score one below-threshold or hard-failure run.
4. Confirm hard failures block closure.
5. Route the failed run to review-manager.
6. Export or identify metrics/reporting path.
7. Return commands, scores, hard failures, and review artifact.
```
