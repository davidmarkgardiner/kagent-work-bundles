# KB + GitLab MCP Work-Agent Checklist

## P0

| Check | Evidence required | Status |
|---|---|---|
| Bundle verifier passes | `bash scripts/verify-bundle.sh` output | TODO |
| GitLab MCP tools available | Tool names or wrapper description | TODO |
| Scoped auth confirmed | Project or repository boundary, no token value | TODO |
| Branch created | Branch name and source target branch | TODO |
| KB docs created or updated | File paths and commit IDs | TODO |
| KB index updated | `docs/platform-kb/INDEX.md` diff or commit | TODO |
| Merge request created | MR URL | TODO |
| Merge request note created | Note body with proof markers | TODO |
| doc2vec/querydoc reindexed | Build output, job name, or index timestamp | TODO |
| Knowledge agent cited hit | Citation to `docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md` | TODO |
| Knowledge agent fallback | `NO_RELEVANT_DOCS` or clear no-docs response | TODO |
| Triage agent uses KB | `KNOWLEDGE_LOOKUP` block with source path | TODO |

## P1

| Check | Evidence required | Status |
|---|---|---|
| kagent UI transcript captured | Screenshot, transcript, or run artifact | TODO |
| A2A transcript captured | Caller, callee, source citation | TODO |
| Dashboard or report link updated | Report includes KB and GitLab evidence | TODO |
| Stale-doc gap route tested | GitLab MCP request for a missing doc | TODO |

## Hard Stops

Stop and report `BLOCKED` if:

- GitLab MCP has no branch/file/MR capability and no approved wrapper exists.
- The token or identity is not scoped to an approved project.
- querydoc cannot be rebuilt or reached from the knowledge agent.
- the knowledge agent answers without citations.
- the general triage or front-door agent has write-capable GitLab tools.
