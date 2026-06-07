# Memory MCP Shared Context Work-Agent Bundle

Purpose: prove agents can persist useful cross-session context safely, recall it
in later workflows, and route memory updates through an approved curator path.

## One-Line Ask

Deploy or verify Memory MCP, seed a safe memory item, recall it from another
agent/session, use it in triage context, and prove writes are curated rather
than letting every agent mutate memory freely.

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
