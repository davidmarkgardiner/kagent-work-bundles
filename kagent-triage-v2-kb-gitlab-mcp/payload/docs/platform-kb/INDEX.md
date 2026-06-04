# Platform Knowledge Base Index

This index is the copyable payload for the Kagent triage v2 KB + GitLab MCP
work-agent bundle.

## Kagent Triage V2 Agent Guidance

| User intent | Primary document | Notes |
|---|---|---|
| Understand Kagent triage v2 | `docs/platform-kb/agents/kagent-triage-v2-overview.md` | Agent roles, safety rules, evidence requirements |
| Update KB docs through GitLab MCP | `docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md` | Branch, file update, MR, index update, querydoc proof markers |
| Query the platform KB through querydoc | `docs/platform-kb/agents/querydoc-knowledge-agent.md` | Runtime path, query contract, cited-hit and no-docs checks |
| Use KB lookup during incident triage | `docs/platform-kb/agents/triage-agent-kb-lookup.md` | When to call the knowledge agent and how to report citations |

## Answering Rules

The knowledge-base agent must:

1. Use the documentation lookup tool before answering platform documentation
   questions.
2. Prefer the most specific document listed in this index.
3. Cite source paths and headings.
4. Say when the docs do not answer the question.
5. Route stale or missing documentation feedback to the approved GitLab MCP
   documentation update workflow instead of mutating Git directly from the chat
   agent.
