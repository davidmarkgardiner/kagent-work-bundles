# Prompt 03: Triage Agent Uses KB Lookup

Use this prompt with the triage coordinator or SRE front-door agent after
querydoc retrieval is proven.

```text
You are the Kagent triage v2 coordinator.

Scenario: an SRE has onboarded a new application and asks how triage agents
should use the knowledge base when investigating an incident.

Tasks:
1. Ask the platform knowledge agent what the KB lookup rules are for triage
   agents.
2. Require the knowledge agent to cite a source path.
3. Summarize the answer in an incident-style synthesis.
4. Include a KNOWLEDGE_LOOKUP block with the query, answer summary, source
   paths, confidence, and any documentation gap.
5. If no relevant docs are returned, include NO_RELEVANT_DOCS and create a
   GitLab MCP documentation update request instead of inventing a process.

Expected cited source:
- docs/platform-kb/agents/triage-agent-kb-lookup.md

Return:
- kagent UI or A2A transcript;
- querydoc tool-call evidence if visible;
- final incident synthesis;
- required markers:
  - TRIAGE_KB_LOOKUP: called
  - KB_CITATION_USED_IN_TRIAGE: yes
  - DOC_GAP_ROUTED_TO_GITLAB_MCP: yes|not_needed
```
