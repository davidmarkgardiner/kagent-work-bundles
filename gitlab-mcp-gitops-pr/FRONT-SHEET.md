# GitLab MCP GitOps PR Work-Agent Bundle

Purpose: prove that a kagent-mounted GitLab MCP specialist can create a
reviewable code, YAML, or documentation change in a sandbox work repository and
leave it for a human to review.

## One-Line Ask

Use GitLab MCP to create a branch, update one safe file, open a merge request,
add an evidence note, and prove the change is reviewable without directly
mutating production.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/gitlab-gitops-pr-request.yaml`
5. `prompts/01-create-reviewable-gitops-pr.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

## Definition Of Done

- GitLab MCP tools discovered.
- Scoped project and identity confirmed without exposing token values.
- Branch created from the target branch.
- File created or updated.
- Merge request opened.
- Merge request note added with proof markers.
- Human review boundary is explicit.
- No cluster mutation is claimed from GitLab write proof alone.

## Required Markers

```text
KAGENT_MCP: called
GITLAB_BRANCH: created
GITLAB_FILE: created_or_updated
GITLAB_MR: created
GITLAB_MR_NOTE: created
HUMAN_REVIEW_REQUIRED: yes
OUTPUT_SANITIZED: yes
```
