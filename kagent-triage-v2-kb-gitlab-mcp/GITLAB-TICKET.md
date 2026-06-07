# GitLab Ticket: Prove KB Update Through GitLab MCP And Querydoc

## Summary

Prove Kagent triage v2 can update KB documents through GitLab MCP and retrieve
them through doc2vec/querydoc.

## Feature

An approved documentation specialist should update KB docs and the index through
a reviewable MR, then the knowledge agent should cite the new content during
triage.

## Evidence Required

- GitLab MCP/server status and tools.
- Branch and changed KB files.
- Updated index.
- MR URL and note.
- Reindex output.
- Cited querydoc result.
- No-docs fallback proof.

## Acceptance Criteria

- GitLab branch/file/MR/note proof captured.
- `docs/platform-kb/INDEX.md` updated.
- Querydoc/doc2vec reindex completed or explicit blocker recorded.
- Knowledge agent returns a cited hit.
- Knowledge agent returns a no-docs fallback for unrelated query.
- Output sanitized.

## Notes

Do not claim proof from local copied files. The work proof requires GitLab MCP
or an approved wrapper plus live querydoc retrieval.
