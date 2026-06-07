# Kagent Triage V2 KB + GitLab MCP

## TL;DR

Proves agents can update platform KB documents through GitLab MCP, rebuild or
refresh doc2vec/querydoc, and retrieve cited answers through the knowledge
agent.

## What This Feature Does

- Creates or updates KB documents under `docs/platform-kb/agents/`.
- Updates the KB index.
- Opens a reviewable GitLab MR.
- Reindexes querydoc/doc2vec.
- Proves cited retrieval and no-docs fallback.

## Evidence To Produce

- GitLab MCP/server tool list.
- Branch, file changes, MR, and note.
- Reindex output.
- Knowledge-agent cited hit.
- No relevant docs fallback.
- Triage-agent KB lookup block.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Execute prompts `01`, `02`, and `03` in order.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

The KB update is reviewable in GitLab, the index is refreshed, and the knowledge
agent can cite the new content from kagent UI or A2A.
