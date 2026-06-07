# Kagent Triage V2 KB + GitLab MCP Work-Agent Bundle

Date: 2026-06-04

Purpose: copy this folder into the work agent context and ask it to recreate the
same knowledge-base update loop in the work environment.

This folder is self-contained. The work agent should not need to browse the
rest of the home-lab repo to understand the task.

## One-Line Ask

Use GitLab MCP to create or update the bundled Kagent triage v2 KB documents in
the work repository, update the KB index, open a reviewable merge request,
rebuild doc2vec/querydoc, and prove the platform knowledge agent can cite the
new documents from kagent UI or A2A.

## Start Here

Read these files in order:

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/kb-update-request.yaml`
5. `prompts/01-create-kb-docs-via-gitlab-mcp.md`
6. `prompts/02-reindex-and-querydoc-proof.md`
7. `prompts/03-triage-agent-kb-lookup.md`
8. `expected/platform-kb-author-agent.yaml`
9. `expected/kb-update-evidence-contract.yaml`
10. `expected/platform-knowledge-agent-query-contract.yaml`
11. `payload/docs/platform-kb/INDEX.md`
12. `payload/docs/platform-kb/agents/*.md`

## Local Bundle Check

Run this before starting work-side live actions:

```bash
bash scripts/verify-bundle.sh
```

Expected:

```text
KB_GITLAB_MCP_WORK_AGENT_BUNDLE_VERIFY: passed
```

This is a static bundle check only. It does not prove live GitLab MCP, querydoc,
or kagent UI access.

## Work-Lab Definition Of Done

The work agent must return evidence for:

- Official GitLab MCP RemoteMCPServer accepted state and tool list.
- If only an approved wrapper or lite GitLab MCP is available, evidence is
  marked `DEMO_ONLY` and full KB GitOps capability remains blocked until the
  official branch/file/MR/note tools are available.
- Source branch created from the target branch.
- KB files created or updated under `docs/platform-kb/agents/`.
- `docs/platform-kb/INDEX.md` updated.
- Merge request opened.
- Merge request note added.
- doc2vec/querydoc database rebuilt or in-cluster index job completed.
- Knowledge agent returns a cited hit for the GitLab MCP KB update document.
- Knowledge agent returns `NO_RELEVANT_DOCS` or equivalent no-docs fallback.
- Triage coordinator uses the cited KB answer in a `KNOWLEDGE_LOOKUP` block.

## Safety Rules

- Use an approved non-production or documentation sandbox project first.
- Use a scoped PAT, OAuth identity, or service identity approved for that work
  repository.
- Do not expose tokens, internal URLs, private hostnames, cluster IPs, tenant
  IDs, subscription IDs, or private project names in reusable evidence.
- Do not give write-capable GitLab tools to front-door or general triage agents.
- Treat GitLab write access as a specialist capability behind review and, for
  remediation flows, HITL.

## What To Copy Into The Work Repo

The desired KB payload is under:

```text
payload/docs/platform-kb/
```

The work agent should create or update those same target paths through GitLab
MCP:

```text
docs/platform-kb/INDEX.md
docs/platform-kb/agents/kagent-triage-v2-overview.md
docs/platform-kb/agents/gitlab-mcp-kb-update-loop.md
docs/platform-kb/agents/querydoc-knowledge-agent.md
docs/platform-kb/agents/triage-agent-kb-lookup.md
```

Do not just copy these files locally and claim success. Local copying is only a
preview. The proof requires GitLab MCP branch, file, MR, note, reindex, and
querydoc citation evidence.
