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

- Official GitLab MCP RemoteMCPServer is Accepted=True and its tool list is
  discovered.
- Required file/branch/MR/note tools are present on the official GitLab MCP, or
  the run is marked BLOCKED.
- Scoped project and identity confirmed without exposing token values.
- Branch created from the target branch.
- File created or updated.
- Merge request opened.
- Merge request note added with proof markers.
- Human review boundary is explicit.
- No cluster mutation is claimed from GitLab write proof alone.

## Official Vs Lite MCP

Use `{{GITLAB_MCP_REMOTE_SERVER_NAME}}` for the real GitOps PR proof. A
`{{GITLAB_LITE_MCP_REMOTE_SERVER_NAME}}` or demo wrapper can be used only to
prove a limited sandbox MR path, and the evidence must label that result
`DEMO_ONLY`. Do not claim full GitOps write capability from a lite wrapper that
cannot create branches, update arbitrary files, or add review notes.

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
