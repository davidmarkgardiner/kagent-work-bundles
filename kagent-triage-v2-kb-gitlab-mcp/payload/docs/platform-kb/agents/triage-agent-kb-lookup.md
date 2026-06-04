# Triage Agent KB Lookup

## Purpose

Triage agents should use the knowledge base when they need platform guidance,
runbooks, previous operating patterns, or onboarding information. This keeps
incident reasoning tied to reviewed documentation instead of free-form memory.

## When To Query The KB

A triage agent should ask the knowledge agent when:

- an alert references a known application or namespace;
- a failure mode resembles an existing runbook;
- a proposed remediation depends on platform policy;
- an SRE asks how to bring an application into Kagent triage v2;
- a specialist is missing context about GitLab, Grafana, doc2vec, querydoc, A2A,
  or HITL workflow expectations;
- the agent is about to recommend a change and needs a cited source.

## Required Response Shape

The triage coordinator should include this section in its incident synthesis:

```text
KNOWLEDGE_LOOKUP:
- query:
- answer_summary:
- source_paths:
- confidence:
- gap_to_document:
```

If the KB does not answer the question, the coordinator should include:

```text
KNOWLEDGE_LOOKUP:
- result: NO_RELEVANT_DOCS
- gap_to_document: <specific missing runbook or platform guide>
- next_action: create a GitLab MCP documentation update request
```

## Example A2A Prompt

```text
Ask the platform knowledge agent how Kagent triage v2 should use GitLab MCP
during a documentation update. Return the cited source path and do not invent a
procedure if the KB does not contain one.
```

## Evidence

The work proof should include:

- the A2A or kagent UI request to the knowledge agent;
- the querydoc tool call result;
- the cited source path;
- the triage synthesis section that used the cited answer;
- the follow-up documentation gap if no relevant doc was found.
