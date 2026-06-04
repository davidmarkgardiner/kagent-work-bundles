# GitLab MCP Knowledge-Base Update Loop

## Purpose

The GitLab MCP knowledge-base update loop lets an approved agent create or
update platform documentation without mutating the knowledge-base runtime
directly. The desired state stays in Git. The vector database is rebuilt from
that Git-backed corpus after review.

## Expected Path

1. A user or agent identifies stale or missing knowledge.
2. The knowledge agent summarizes the gap and prepares a documentation update
   request.
3. A GitOps documentation agent uses GitLab MCP to create a sandbox branch.
4. The agent creates or updates Markdown files under `docs/platform-kb/`.
5. The agent updates `docs/platform-kb/INDEX.md` if the new document should be
   discoverable by query routing.
6. The agent opens a merge request and adds an evidence note.
7. A human reviews and merges the change.
8. The doc2vec indexer rebuilds `platform-kb.db`.
9. querydoc serves the rebuilt database to the platform knowledge agent.

## Required GitLab MCP Capabilities

The ideal GitLab MCP server exposes these tools:

- list projects;
- inspect a project;
- create a branch;
- create or update a file;
- create a merge request;
- add a merge request note.

If the work MCP only exposes issue tools, use an approved wrapper MCP or an
approved workflow job that calls GitLab REST APIs. The definition of done is the
same: the change must appear as a reviewable branch and merge request, not as a
direct local file edit.

## Required Proof Markers

The work agent should return these markers in the evidence bundle:

- `KAGENT_MCP: called`
- `GITLAB_BRANCH: created`
- `GITLAB_FILE: created_or_updated`
- `KB_INDEX_UPDATED: yes`
- `GITLAB_MR: created`
- `GITLAB_MR_NOTE: created`
- `QUERYDOC_REINDEXED: yes`
- `KB_CITED_HIT: yes`
- `NO_RELEVANT_DOCS: yes`

## Guardrails

- Use a dedicated sandbox project or approved documentation repository.
- Use a project-scoped identity with the minimum required write permissions.
- Do not expose write-capable GitLab tools to the front-door or general triage
  agents.
- Do not commit secrets, internal URLs, private hostnames, or cluster IPs.
- Do not mark the KB loop complete until the querydoc path proves retrieval from
  the updated corpus.

## Example User Request

```text
Create a knowledge-base document that explains how Kagent triage v2 uses the
knowledge agent during incident triage. Update the KB index, open a GitLab merge
request, rebuild the doc2vec database, and prove the knowledge agent can cite
the new document.
```
