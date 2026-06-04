# Querydoc Knowledge Agent

## Purpose

The platform knowledge agent answers documentation questions from the Git-backed
platform KB. It uses the upstream doc2vec/querydoc pattern rather than a custom
retrieval service.

## Runtime Path

```text
docs/platform-kb
  -> doc2vec indexer
  -> platform-kb.db
  -> querydoc MCP server
  -> RemoteMCPServer
  -> platform-knowledge-agent
  -> kagent UI or A2A caller
```

## Query Contract

For platform documentation questions, the agent should call
`query_documentation` with:

- `productName: platform-kb`
- `version: current`
- `dbName: platform-kb.db`

The answer must cite source paths and headings. If retrieval does not answer the
question, the agent should say that clearly and route the gap to the
documentation update workflow.

## Proof Queries

Use these two checks after any index rebuild:

| Case | Question | Expected result |
|---|---|---|
| Cited hit | How does Kagent triage v2 use GitLab MCP to update the KB? | Answer cites `docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md` |
| No-docs fallback | How does the platform operate a fictional service not present in the corpus? | Answer returns `NO_RELEVANT_DOCS` or a clear no-docs fallback with no invented citation |

## Operating Notes

- The knowledge agent is read-only.
- It should not push to Git, mutate Kubernetes resources, or create Azure
  resources.
- Stale-document feedback should become a GitLab MCP documentation update
  request.
- Triage agents can call the knowledge agent over A2A when they need runbook or
  platform guidance.
