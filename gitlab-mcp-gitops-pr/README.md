# GitLab MCP GitOps PR

## TL;DR

Proves a kagent-mounted GitLab capability can create a reviewable branch, file
change, merge request, and MR note instead of mutating production directly.

## What This Feature Does

- Discovers the GitLab MCP or approved GitLab API wrapper tools.
- Creates a source branch from an approved target branch.
- Creates or updates one safe file.
- Opens a merge request.
- Adds an evidence note for human review.

## Evidence To Produce

- GitLab MCP/server identity and tool list.
- Sandbox project and target branch.
- Source branch, file path, commit ID.
- MR URL and note body.
- Human review boundary.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Read `OFFICIAL-GITLAB-MCP-SPIKE-2026-06-07.md`.
3. Use `WORK-AGENT-START-PROMPT.md`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

A reviewable MR exists, evidence markers are present, and the output clearly
states whether the official hosted MCP or an approved wrapper was used.
