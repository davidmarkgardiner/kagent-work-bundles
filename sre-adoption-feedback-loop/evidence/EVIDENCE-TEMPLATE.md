# SRE Adoption Feedback Loop Evidence

```text
SRE_OWNER_IDENTIFIED: yes
APPLICATION_SELECTED: yes
FIRST_CONTACT_RUN_COMPLETED: yes
CHAOS_OR_INCIDENT_EXERCISE_COMPLETED: yes
KAGENT_WORKFLOW_USED_BY_SRE: yes
FEEDBACK_CAPTURED: yes
IMPROVEMENT_ITEM_ROUTED: yes
ADOPTION_REPORT_CREATED: yes
DASHBOARD_OR_METRICS_UPDATED: yes_or_not_available
OUTPUT_SANITIZED: yes
```

## Summary

- SRE owner/team: `{{SRE_OWNER}}` / `{{SRE_TEAM}}`
- Application: `{{APPLICATION_NAME}}`
- Namespace/workload: `{{APPLICATION_NAMESPACE}}` / `{{APPLICATION_WORKLOAD}}`
- Adoption window: `{{ADOPTION_WINDOW}}`
- Game-day or incident ID: `{{GAME_DAY_ID}}`

## First Contact

- Prompt path or transcript: `{{FIRST_CONTACT_PROMPT_OR_TRANSCRIPT}}`
- Failure modes identified: `{{FAILURE_MODES}}`
- Existing dashboards/runbooks/alerts mapped: `{{EXISTING_CONTEXT_SUMMARY}}`
- Tooling mapped: `{{TOOLING_SUMMARY}}`

## Exercise

- Exercise type: `{{EXERCISE_TYPE}}`
- Exercise status: `completed|blocked`
- Run/workflow/incident ID: `{{RUN_OR_WORKFLOW_ID}}`
- Blocker, if any: `{{BLOCKER_OR_NONE}}`
- Evidence pack: `{{EVIDENCE_PACK_LINK_OR_PATH}}`
- Eval score or hard-gate result: `{{EVAL_RESULT_OR_NOT_AVAILABLE}}`

## SRE Usage Proof

- SRE action: `{{SRE_ACTION_SUMMARY}}`
- Review/approval/comment link: `{{SRE_REVIEW_LINK_OR_NOT_AVAILABLE}}`
- Human approval route: `{{APPROVAL_CHANNEL}}`
- Did SRE use or review the workflow: `yes|no`

## Feedback

- Feedback captured in: `{{FEEDBACK_CAPTURE_LOCATION}}`
- Feedback categories: `{{FEEDBACK_CATEGORIES}}`
- Top feedback item: `{{TOP_FEEDBACK_ITEM}}`
- Agent answer quality: `correct|partially_correct|incorrect|not_scored`
- Missing or weak areas: `{{MISSING_OR_WEAK_AREAS}}`

## Routed Improvements

- GitLab issue/MR/backlog item: `{{IMPROVEMENT_ITEM_LINK_OR_PATH}}`
- Improvement type: `kb|skill|eval|dashboard|policy|workflow|access|other`
- Owner: `{{IMPROVEMENT_OWNER}}`
- Next action: `{{NEXT_ACTION}}`

## Adoption Report

- Report location: `{{ADOPTION_REPORT_LOCATION}}`
- Dashboard or metrics update: `{{DASHBOARD_OR_METRICS_LOCATION_OR_NOT_AVAILABLE}}`
- Current adoption status: `not_started|trial_started|in_use|blocked`
- Open blockers: `{{OPEN_BLOCKERS_OR_NONE}}`
