# GitLab Ticket: Prove GitLab MCP GitOps PR Path

## Summary

Prove that kagent can create a safe, reviewable GitOps change through GitLab MCP
or an approved GitLab MCP/API wrapper.

## Feature

The GitOps specialist should create a branch, update one safe file, open an MR,
and add an evidence note so humans can review proposed changes before anything
is applied.

## Evidence Required

- GitLab MCP/server name and discovered tools.
- Auth mode without token values.
- Branch name and target branch.
- Changed file path and commit ID.
- MR URL.
- MR note body.
- Official MCP vs wrapper classification.

## Acceptance Criteria

- `KAGENT_MCP: called`
- `GITLAB_BRANCH: created`
- `GITLAB_FILE: created_or_updated`
- `GITLAB_MR: created`
- `GITLAB_MR_NOTE: created`
- `HUMAN_REVIEW_REQUIRED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not claim official hosted GitLab MCP unless `RemoteMCPServer Accepted=True`
and the required tools are discovered. Wrapper/API proof is valid but must be
labelled accurately.
