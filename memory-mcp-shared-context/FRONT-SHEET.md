# Memory MCP Shared Context Work-Agent Bundle

Purpose: prove agents can persist useful cross-session context safely, recall it
in later workflows, and route memory updates through an approved curator path.

## One-Line Ask

Deploy or verify Memory MCP, seed a safe memory item, recall it from another
agent/session, use it in triage context, and prove writes are curated rather
than letting every agent mutate memory freely.

## Start Here

1. `FRONT-SHEET.md`
2. `WORK-AGENT-START-PROMPT.md`
3. `CHECKLIST.md`
4. `requests/memory-shared-context-request.yaml`
5. `prompts/01-prove-memory-shared-context.md`
6. `payload/REFERENCE.md`
7. `evidence/EVIDENCE-TEMPLATE.md`

Static verification proves this bundle is internally consistent. It does not
prove live memory MCP, kagent, persistence, curator, or triage behavior.

## Required Markers

```text
MEMORY_MCP_AVAILABLE: yes
MEMORY_SEEDED: yes
MEMORY_RECALLED: yes
MEMORY_USED_IN_TRIAGE: yes
CURATOR_PATH_DEFINED: yes
DANGEROUS_MEMORY_WRITE_BLOCKED: yes
OUTPUT_SANITIZED: yes
```
